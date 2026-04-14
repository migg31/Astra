"""PDF parser for EASA CS documents (CS-25, CS-ACNS, etc.).

Extracts regulatory nodes (CS, AMC, GM) from consolidated PDF amendments
published by EASA. Uses font-size heuristics to identify article headings.

Font signature observed in CS-25 Amendment 28:
  Calibri-Bold  20pt  → Subpart heading  (ignored as GROUP)
  Calibri-Bold  18pt  → Section heading  (ignored as GROUP)
  Calibri-Bold  16pt  → Article heading  (CS / AMC / GM)
  Calibri       11pt  → Body text
  Calibri-*      9pt  → Page header/footer (ignored)
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from backend.harvest.models import ParsedNode, ParseResult

# ── Constants ─────────────────────────────────────────────────────────────────

ARTICLE_SIZE_MIN = 13.0   # headings >= this size are article candidates
BODY_SIZE_MIN = 9.5       # body text >= this size (excludes 9pt headers/footers)
PAGE_HEADER_SIZE_MAX = 9.5  # headers/footers at 9pt are ignored

# Patterns to identify node type from heading text
_CS_RE  = re.compile(r"^CS[\s\-]", re.IGNORECASE)
_AMC_RE = re.compile(r"^AMC[\s\d\-]", re.IGNORECASE)
_GM_RE  = re.compile(r"^GM[\s\d]",  re.IGNORECASE)

# Pattern to detect CS-ACNS article references (older Verdana PDFs where size == body)
# e.g. "CS ACNS.A.GEN.001   Applicability" or "AMC1 ACNS.B.DLS.B1.020 ..."
_ACNS_HEADING_RE = re.compile(
    r"^((?:CS|AMC\d*|GM\d*)\s+ACNS\.\S+)",
    re.IGNORECASE,
)

# Pattern to detect CS-25 legacy article headings (old Arial ~9pt bold PDFs)
# e.g. "CS 25.1 Applicability"  "AMC 25.101 General"  "GM 25.1 ..."
_CS25_LEGACY_RE = re.compile(
    r"^((?:CS|AMC|GM)\s+25[\.\-]\S+)",
    re.IGNORECASE,
)

# Pattern to detect CS-AWO article headings
# e.g. "CS AWO.A.ALS.101"  "AMC1 AWO.B.CAT.230"  "GM1 AWO.D.LVO.105"
_AWO_HEADING_RE = re.compile(
    r"^((?:CS|AMC\d*|GM\d*)\s+AWO\.\S+)",
    re.IGNORECASE,
)

# Pattern to extract reference code from heading
# e.g. "CS 25.581 Lightning protection" → "CS 25.581"
# e.g. "AMC 25.581 Lightning protection" → "AMC 25.581"
# e.g. "AMC 25-1 ..." → "AMC 25-1"
# e.g. "AMC to Appendix S, S25.30(a) ..." → "AMC to Appendix S, S25.30(a)"
_REF_RE = re.compile(
    r"^((?:CS|AMC|GM)[\s\-][\w\.\-]+(?:\([^)]*\))*(?:[\.-]\d+)*)",
    re.IGNORECASE,
)
_REF_APPENDIX_RE = re.compile(
    r"^((?:AMC|GM) to [^,\n]+(?:,[^\n]+)?)",
    re.IGNORECASE,
)

# Heading sizes that denote SUBPART (top level) or SECTION (sub-level)
_SUBPART_SIZE_MIN  = 19.5   # e.g. CS-AWO "SUBPART A" at 20pt
_SECTION_SIZE_MIN  = 17.5   # e.g. CS-AWO "SECTION 1" at 17.6–18pt
_STRUCTURAL_SIZE_MIN = _SECTION_SIZE_MIN   # kept for other parsers

# Ignore page header/footer patterns
_PAGE_HEADER_RE = re.compile(
    r"^(Annex to ED Decision|Page \d+ of \d+|CS-\d+\s+Amendment|CS-ACNS"
    r"|BOOK\s+\d+|CS[\s\-\u2013]+25$|\d+[\-\u2013][A-Z][\-\u2013]\d+"
    r"|(CS|AMC)\s+25\.\d+.*\.\.\.\.)",
    re.IGNORECASE,
)


def _node_type(heading: str) -> str | None:
    if _CS_RE.match(heading):
        return "CS"
    if _AMC_RE.match(heading):
        return "AMC"
    if _GM_RE.match(heading):
        return "GM"
    return None


def _reference_code(heading: str) -> str:
    h = heading.strip()
    m = _REF_APPENDIX_RE.match(h)
    if m:
        return m.group(1).strip()[:120]
    m = _REF_RE.match(h)
    if m:
        return m.group(1).strip()
    return h.split("\n")[0][:80]


def _title(heading: str) -> str:
    ref = _reference_code(heading)
    title = heading[len(ref):].strip()
    return title or ref


def _hash(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()  # noqa: S324


def _is_page_noise(text: str) -> bool:
    return bool(_PAGE_HEADER_RE.match(text.strip()))


@dataclass
class _Block:
    text: str
    size: float
    bold: bool


def _extract_blocks(page: pymupdf.Page) -> list[_Block]:
    """Extract text blocks with their dominant font size and bold flag.

    Groups spans by Y-coordinate across all PDF blocks on the page to handle
    justified text where PyMuPDF fragments a single visual line into multiple
    blocks (one per word) due to variable inter-word spacing.
    """
    # ── Step 1: collect all (y_key, x, text, size, bold) from every span ──────
    Y_SNAP = 2.0  # px tolerance to consider two spans on the same line
    raw: list[tuple[float, float, str, float, bool]] = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for line in b.get("lines", []):
            lbbox = line.get("bbox", [0, 0, 0, 0])
            y_center = (lbbox[1] + lbbox[3]) / 2
            for span in line.get("spans", []):
                t = span["text"].replace("\xa0", " ")
                t = " ".join(t.split())
                if not t:
                    continue
                raw.append((y_center, span["bbox"][0], t, span["size"], "Bold" in span["font"]))

    if not raw:
        return []

    # ── Step 1b: merge superscript spans (sz < 8) into the preceding token ───
    # e.g. "10" (sz=10) + "-6" (sz=6.5) → "10-6"
    SUPERSCRIPT_MAX = 8.0
    merged: list[tuple[float, float, str, float, bool]] = []
    for item in raw:
        if merged and item[3] < SUPERSCRIPT_MAX:
            prev = merged[-1]
            # Only merge if very close X (adjacent superscript)
            if abs(item[1] - (prev[1] + prev[3] * 0.55 * len(prev[2]))) < 10:
                merged[-1] = (prev[0], prev[1], prev[2] + item[2], prev[3], prev[4])
                continue
        merged.append(item)
    raw = merged

    # ── Step 2: group spans by Y (snap within Y_SNAP tolerance) ──────────────
    raw.sort(key=lambda r: (r[0], r[1]))  # sort by y then x

    groups: list[list[tuple[float, float, str, float, bool]]] = []
    current: list[tuple[float, float, str, float, bool]] = [raw[0]]
    for item in raw[1:]:
        if abs(item[0] - current[0][0]) <= Y_SNAP:
            current.append(item)
        else:
            groups.append(current)
            current = [item]
    groups.append(current)

    # ── Step 3: merge Y-groups into logical paragraph blocks ─────────────────
    # Consecutive Y-groups that share dominant size+bold → same block
    # Column gap threshold: if two spans on the same row are separated by > this
    # many points, they belong to different table columns (use \t as separator).
    COL_GAP = 30.0
    # Pattern that typically starts a table-value column (number or "Not applicable")
    _COL_VAL_RE = re.compile(r"^\d|^Not\s+applicable", re.IGNORECASE)
    line_records: list[tuple[str, float, bool]] = []
    for grp in groups:
        grp.sort(key=lambda r: r[1])  # sort by x
        sizes = [r[3] for r in grp]
        bolds = [r[4] for r in grp]
        avg_size = sum(sizes) / len(sizes)
        is_bold = sum(bolds) > len(bolds) / 2

        # Build line text: group consecutive spans into column chunks,
        # separated by \t when a large horizontal gap AND the next chunk
        # looks like a table value (digit or "Not applicable").
        col_chunks: list[list[str]] = [[]]
        prev_x_end: float = grp[0][1]
        for r in grp:
            x_start = r[1]
            gap = x_start - prev_x_end
            is_col_break = gap > COL_GAP and _COL_VAL_RE.match(r[2])
            if col_chunks and is_col_break:
                col_chunks.append([])
            col_chunks[-1].append(r[2])
            prev_x_end = x_start + r[3] * 0.55 * len(r[2])

        line_text = "\t".join(" ".join(ch) for ch in col_chunks if ch)

        line_records.append((line_text, round(avg_size, 1), is_bold))

    # Group consecutive lines with same size+bold into a single _Block
    # Lines containing \t (table columns) are never merged with neighbors.
    blocks: list[_Block] = []
    i = 0
    while i < len(line_records):
        line_text, sz, bold = line_records[i]
        if "\t" in line_text:
            # Table row — keep as its own block
            if line_text.strip():
                blocks.append(_Block(text=line_text.strip(), size=sz, bold=bold))
            i += 1
            continue
        block_lines = [line_text]
        j = i + 1
        while j < len(line_records):
            next_text, next_sz, next_bold = line_records[j]
            if "\t" in next_text:
                break  # next line is a table row → stop merging
            if abs(next_sz - sz) < 0.5 and next_bold == bold:
                block_lines.append(next_text)
                j += 1
            else:
                break
        text = "\n".join(block_lines).strip()
        if text:
            blocks.append(_Block(text=text, size=sz, bold=bold))
        i = j

    return blocks


def parse_cs_pdf(pdf_path: Path, *, regulatory_source: str | None = None) -> ParseResult:
    """Parse a CS PDF and return a ParseResult with nodes extracted."""
    doc = pymupdf.open(str(pdf_path))

    # Extract version label and pub date from page 1
    first_page_text = doc[0].get_text()
    version_label = _extract_version_label(first_page_text)

    # Build document title prefix — used as root of hierarchy_path so the frontend
    # can identify this document as a browsable source (matches catalog source_root)
    source_prefix = regulatory_source.split(" ")[0] if regulatory_source else "CS"
    if version_label:
        version_label = " ".join(version_label.replace("\xa0", " ").split())
    doc_title = f"{source_prefix} {version_label}".strip() if version_label else (regulatory_source or "CS Document")

    nodes: list[ParsedNode] = []

    current_heading: str | None = None
    current_type: str | None = None
    current_body_parts: list[str] = []
    current_subpart: str = ""   # top-level structural label (SUBPART A, GENERAL AMC…)
    current_section: str = ""   # sub-level structural label (SECTION 1, CATEGORY II…)
    current_hierarchy: str = doc_title  # default: just the doc title as root
    legacy_mode: bool = False  # True when current article was detected by pattern (small fonts)
    in_toc: bool = True  # True until we encounter the first real structural heading

    def _flush() -> None:
        if current_heading is None or current_type is None:
            return
        ref = _reference_code(current_heading)
        title = _title(current_heading)
        body = "\n".join(current_body_parts).strip()
        nodes.append(ParsedNode(
            node_type=current_type,
            reference_code=ref,
            title=title,
            content_text=body,
            content_hash=_hash(body),
            hierarchy_path=current_hierarchy,
            content_html=None,
            regulatory_source=regulatory_source,
        ))

    for page_num in range(doc.page_count):
        blocks = _extract_blocks(doc[page_num])

        for blk in blocks:
            text = blk.text.strip()
            size = blk.size

            if _is_page_noise(text):
                continue

            # Legacy pattern detection (small-font PDFs) — must run before size filters
            is_article_by_pattern = blk.bold and (
                bool(_ACNS_HEADING_RE.match(text))
                or bool(_CS25_LEGACY_RE.match(text))
                or bool(_AWO_HEADING_RE.match(text))
            )
            if is_article_by_pattern and not in_toc:
                node_type = _node_type(text)
                if node_type:
                    _flush()
                    current_heading = text.replace("\n", " ").strip()
                    current_type = node_type
                    current_body_parts = []
                    legacy_mode = True
                    continue

            # Skip page headers/footers (9pt italic) — after pattern check
            if size <= PAGE_HEADER_SIZE_MAX:
                continue

            # Structural headings — two levels for CS-AWO style docs
            if size >= _SECTION_SIZE_MIN and blk.bold:
                _flush()
                current_heading = None
                current_type = None
                current_body_parts = []
                label = " ".join(text.replace("\xa0", " ").replace("\n", " ").split())
                # Collapse letter-spaced uppercase words: 'S UBPART' → 'SUBPART'
                label = re.sub(r'\b([A-Z]) ([A-Z]{2,})\b', r'\1\2', label)
                if size >= _SUBPART_SIZE_MIN:
                    # Top-level: SUBPART A, GENERAL AMC, etc.
                    current_subpart = label
                    current_section = ""
                    current_hierarchy = doc_title + " / " + label
                else:
                    # Sub-level: SECTION 1, CATEGORY II, VISIBILITY, etc.
                    current_section = label
                    if current_subpart:
                        current_hierarchy = doc_title + " / " + current_subpart + " / " + label
                    else:
                        current_hierarchy = doc_title + " / " + label
                legacy_mode = False
                # Only exit ToC mode when we hit a real document heading
                # (SUBPART, SECTION, GENERAL — not DISCLAIMER/TABLE OF CONTENTS/NOTE…)
                if re.search(r'\b(SUBPART|SECTION|GENERAL|CHAPTER)\b', label, re.IGNORECASE):
                    in_toc = False
                continue

            # Skip article headings until the first real SUBPART/SECTION is seen
            # (avoids capturing ToC entries as article nodes)
            if in_toc:
                continue

            # Article heading — detected by font size (modern Calibri PDFs)
            if size >= ARTICLE_SIZE_MIN and blk.bold:
                # Block may be prefixed by a section label on its own line
                # e.g. "GENERAL\nCS AWO.A.ALS.101 Applicability" — strip prefix line
                # Also strip trailing tab-separated annotations ("ED Decision 2022/..")
                heading_text = text.split("\t")[0].strip()
                if "\n" in heading_text:
                    lines = heading_text.splitlines()
                    for li, ln in enumerate(lines):
                        if _node_type(ln.strip()):
                            heading_text = "\n".join(lines[li:]).strip()
                            break
                node_type = _node_type(heading_text)
                if node_type:
                    _flush()
                    current_heading = heading_text.replace("\n", " ").strip()
                    current_type = node_type
                    current_body_parts = []
                    legacy_mode = False
                    continue

            # Body text — bypass size filter in legacy mode
            if current_heading is not None and (legacy_mode or size >= BODY_SIZE_MIN):
                current_body_parts.append(text)

    _flush()

    # Drop spurious nodes: no digit in ref (e.g. "CS S") or empty body (TOC line false positives)
    nodes = [n for n in nodes if re.search(r"\d", n.reference_code) and n.content_text.strip()]

    # Deduplicate by (node_type, reference_code) — keep last occurrence
    seen: dict[tuple[str, str], ParsedNode] = {}
    for n in nodes:
        seen[(n.node_type, n.reference_code)] = n
    nodes = list(seen.values())

    return ParseResult(
        nodes=nodes,
        edges=[],
        source_document_hash="",
        source_document_title=doc_title,
        source_version=version_label,
        source_pub_time=None,
    )


def _extract_version_label(first_page_text: str) -> str | None:
    """Extract 'Amendment 28' or 'Initial Issue' from page 1 text."""
    m = re.search(r"(Amendment\s+\d+|Initial\s+Issue|Issue\s+\d+)", first_page_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None
