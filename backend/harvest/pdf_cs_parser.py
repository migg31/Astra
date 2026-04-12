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

# Heading sizes that denote SUBPART or SECTION (structural, not articles)
_STRUCTURAL_SIZE_MIN = 17.5

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
    """Extract text blocks with their dominant font size and bold flag."""
    blocks: list[_Block] = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        lines_text: list[str] = []
        sizes: list[float] = []
        bolds: list[bool] = []
        for line in b.get("lines", []):
            line_parts: list[str] = []
            for span in line.get("spans", []):
                t = span["text"]
                if not t.strip():
                    continue
                line_parts.append(t)
                sizes.append(span["size"])
                bolds.append("Bold" in span["font"])
            if line_parts:
                lines_text.append("".join(line_parts))
        if not lines_text:
            continue
        text = "\n".join(lines_text).strip()
        if not text:
            continue
        avg_size = sum(sizes) / len(sizes) if sizes else 0
        dominant_bold = sum(bolds) > len(bolds) / 2
        blocks.append(_Block(text=text, size=avg_size, bold=dominant_bold))
    return blocks


def parse_cs_pdf(pdf_path: Path, *, regulatory_source: str | None = None) -> ParseResult:
    """Parse a CS PDF and return a ParseResult with nodes extracted."""
    doc = pymupdf.open(str(pdf_path))

    # Extract version label and pub date from page 1
    first_page_text = doc[0].get_text()
    version_label = _extract_version_label(first_page_text)

    nodes: list[ParsedNode] = []

    current_heading: str | None = None
    current_type: str | None = None
    current_body_parts: list[str] = []
    current_hierarchy: str = ""
    legacy_mode: bool = False  # True when current article was detected by pattern (small fonts)

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
                bool(_ACNS_HEADING_RE.match(text)) or bool(_CS25_LEGACY_RE.match(text))
            )
            if is_article_by_pattern:
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

            # Structural heading (subpart / section) — flush current, update hierarchy
            if size >= _STRUCTURAL_SIZE_MIN and blk.bold:
                _flush()
                current_heading = None
                current_type = None
                current_body_parts = []
                current_hierarchy = text.replace("\n", " ").strip()
                legacy_mode = False
                continue

            # Article heading — detected by font size (modern Calibri PDFs)
            if size >= ARTICLE_SIZE_MIN and blk.bold:
                node_type = _node_type(text)
                if node_type:
                    _flush()
                    current_heading = text.replace("\n", " ").strip()
                    current_type = node_type
                    current_body_parts = []
                    legacy_mode = False
                    continue

            # Body text — bypass size filter in legacy mode
            if current_heading is not None and (legacy_mode or size >= BODY_SIZE_MIN):
                current_body_parts.append(text)

    _flush()

    # Deduplicate by (node_type, reference_code) — keep last occurrence
    seen: dict[tuple[str, str], ParsedNode] = {}
    for n in nodes:
        seen[(n.node_type, n.reference_code)] = n
    nodes = list(seen.values())

    return ParseResult(
        nodes=nodes,
        edges=[],
        source_document_hash="",
        source_document_title=f"{regulatory_source.split(' ')[0]} {version_label}".strip() if version_label else regulatory_source,
        source_version=version_label,
        source_pub_time=None,
    )


def _extract_version_label(first_page_text: str) -> str | None:
    """Extract 'Amendment 28' or 'Initial Issue' from page 1 text."""
    m = re.search(r"(Amendment\s+\d+|Initial\s+Issue|Issue\s+\d+)", first_page_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None
