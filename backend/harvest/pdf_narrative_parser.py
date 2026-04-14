"""Parser for EASA narrative PDFs (ED Decisions, standalone AMC, GM docs).

These are NOT Easy Access Rules — they use numbered sections (1, 1.1, 1.2.3...)
with bold headings and narrative body text. No CS/AMC/IR prefixed codes.

Each numbered section becomes one ParsedNode of type AMC (default) or GM.
The reference_code is the section number, e.g. "1.1", "4.3.2".
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from backend.harvest.models import ParsedNode, ParseResult

_SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)(?:\s+(.+))?$")
_PAGE_FOOTER_RE = re.compile(
    r"^(Page\s+\d+\s+of\s+\d+|Powered by EASA|©\s*\d{4}|Annex\s+(I|II|III|IV|V|VI|VII)\s+to\b)", re.IGNORECASE
)
_ANNEX_HEADER_RE = re.compile(r"^(AMC|GM)\s+([\d]+(?:[\s\-\.]+\d+)*)\s*$")  # e.g. "AMC 2026", "AMC 20-26"
_APPENDIX_RE = re.compile(r"^(Appendix\s+\d+)\s*$", re.IGNORECASE)  # e.g. "Appendix 2"
_FOOTNOTE_RE = re.compile(r"^\d+\s+[A-Z]")  # footnote lines: "1 Regulation...", "2 Commission..."
_TOC_DOT_RE = re.compile(r"\.{4,}")  # lines of dots = TOC
_SMALL_CAP_SIZE = 8.5  # spans below this are "small caps" artifacts — skip


@dataclass
class _Line:
    text: str
    bold: bool
    size: float


def _extract_lines(page: pymupdf.Page) -> list[_Line]:
    """Extract lines from a page, merging small-caps spans with their predecessor."""
    raw: list[_Line] = []
    for block in page.get_text("dict")["blocks"]:
        if block["type"] != 0:
            continue
        for line in block["lines"]:
            parts: list[tuple[str, bool, float]] = []
            for span in line["spans"]:
                txt = span["text"].replace("\xa0", " ").replace("\xad", "-")
                if not txt.strip():
                    continue
                bold = bool(span["flags"] & (2**4))
                sz = span["size"]
                parts.append((txt, bold, sz))
            if not parts:
                continue
            # Merge small-caps (sz < _SMALL_CAP_SIZE) into previous span
            merged: list[tuple[str, bool, float]] = []
            for txt, bold, sz in parts:
                if merged and sz < _SMALL_CAP_SIZE:
                    prev_txt, prev_bold, prev_sz = merged[-1]
                    merged[-1] = (prev_txt + txt, prev_bold, prev_sz)
                else:
                    merged.append((txt, bold, sz))
            # Build line: majority bold, avg size
            line_text = re.sub(r" {2,}", " ", " ".join(t for t, _, _ in merged)).strip()
            line_bold = sum(1 for _, b, _ in merged if b) > len(merged) / 2
            line_size = merged[0][2] if merged else 10.0
            if line_text:
                raw.append(_Line(text=line_text, bold=line_bold, size=line_size))
    return raw


def _is_heading(line: _Line) -> re.Match | None:
    """Return section match if this line looks like a numbered heading."""
    if not line.bold:
        return None
    txt = line.text.strip()
    if _TOC_DOT_RE.search(txt):
        return None  # TOC line
    return _SECTION_RE.match(txt)


def _section_depth(code: str) -> int:
    return len(code.split("."))


def _hierarchy_path(doc_title: str, ancestors: list[tuple[str, str]]) -> str:
    parts = [doc_title] + [f"{code} {title}".strip() for code, title in ancestors]
    return " / ".join(p for p in parts if p)


def parse_narrative_pdf(
    path: Path,
    *,
    regulatory_source: str = "",
    node_type: str = "AMC",
) -> ParseResult:
    """Parse a numbered-section PDF into ParsedNodes (one per section)."""
    doc = pymupdf.open(str(path))
    result = ParseResult()
    result.source_document_title = regulatory_source or path.stem

    # Detect document title from page 1 bold spans before first section
    title_parts: list[str] = []
    seen_title: set[str] = set()
    first_page_lines = _extract_lines(doc[0])
    for ln in first_page_lines:
        m = _is_heading(ln)
        if m:
            break
        txt = ln.text.strip()
        if ln.bold and not _PAGE_FOOTER_RE.match(txt) and txt not in seen_title:
            title_parts.append(txt)
            seen_title.add(txt)
    if title_parts:
        result.source_document_title = " ".join(title_parts[:3])  # first 3 unique bold lines

    # ── Pass 1: collect all lines across pages ────────────────────────────
    # Lines tagged with optional annex_prefix (e.g. "AMC 2026", "AMC 2027")
    all_lines: list[tuple[_Line, str, str]] = []  # (line, annex_prefix, appendix_label)
    current_annex = regulatory_source  # default = source name
    current_appendix: str = ""  # e.g. "Appendix 2"
    for page in doc:
        page_lines = _extract_lines(page)
        # Detect annex/appendix from the first few lines of the page (page header area)
        # Headers look like: "AMC 2026" / "Appendix 2" / "Page X of Y"
        header_consumed = 0
        for hi, hl in enumerate(page_lines[:4]):
            htxt = hl.text.strip()
            m_hdr = _ANNEX_HEADER_RE.match(htxt)
            if m_hdr:
                new_annex = f"{m_hdr.group(1)} {m_hdr.group(2)}".strip()
                if new_annex != current_annex:
                    current_annex = new_annex
                    current_appendix = ""  # reset appendix on doc change
                header_consumed = hi + 1
                continue
            m_app = _APPENDIX_RE.match(htxt)
            if m_app:
                new_app = m_app.group(1).strip().title()  # normalise to "Appendix 2"
                if new_app != current_appendix:
                    current_appendix = new_app
                header_consumed = hi + 1
                continue
            # Page N of M → skip
            if re.match(r'^Page\s+\d+\s+of\s+\d+', htxt, re.IGNORECASE):
                header_consumed = hi + 1
                continue
            break  # first non-header line — stop scanning
        page_lines = page_lines[header_consumed:]

        for ln in page_lines:
            txt = ln.text.strip()
            if not txt:
                continue
            if _PAGE_FOOTER_RE.match(txt):
                continue
            if _TOC_DOT_RE.search(txt):
                continue
            all_lines.append((ln, current_annex, current_appendix))

    # ── Pass 2: segment into sections ────────────────────────────────────
    # Each section: (annex_prefix, code, title, body_lines)
    sections: list[tuple[str, str, str, str, list[str]]] = []  # (annex, appendix, code, title, body)
    current_code: str | None = None
    current_title: str = ""
    current_body: list[str] = []
    current_pfx: str = regulatory_source
    current_app: str = ""

    for ln, annex_pfx, app_label in all_lines:
        m = _is_heading(ln)
        if m:
            code = m.group(1)
            heading_rest = (m.group(2) or "").strip()
            if current_code is not None:
                sections.append((current_pfx, current_app, current_code, current_title, current_body))
            current_code = code
            current_title = heading_rest
            current_body = []
            current_pfx = annex_pfx
            current_app = app_label
        else:
            if current_code is None:
                continue  # preamble before first section
            if not current_title and ln.bold:
                current_title = ln.text.strip()
            else:
                current_body.append(ln.text.strip())

    if current_code is not None:
        sections.append((current_pfx, current_app, current_code, current_title, current_body))

    if not sections:
        return result

    # ── Pass 3: build hierarchy and ParsedNodes ──────────────────────────
    # Stack keyed by (annex_prefix, code) to reset hierarchy on annex change
    ancestor_stack: list[tuple[str, str]] = []
    last_annex: str = ""
    last_appendix: str = ""
    seen_refs: dict[str, int] = {}  # ref_code -> count for dedup

    for annex_pfx, app_label, code, title, body_lines in sections:
        depth = _section_depth(code)

        # Reset hierarchy when annex or appendix changes
        if annex_pfx != last_annex or app_label != last_appendix:
            ancestor_stack = []
            last_annex = annex_pfx
            last_appendix = app_label

        # Skip TOC ghost entries (no title and no body)
        content = "\n".join(body_lines).strip()
        if not title and not content:
            continue
        # Skip titleless sections whose body looks like footnotes ("1 Regulation...", "2 Commission...")
        if not title and content and _FOOTNOTE_RE.match(content.split("\n")[0].strip()):
            continue

        # Trim ancestor stack to current depth
        while len(ancestor_stack) >= depth:
            ancestor_stack.pop()

        # Build hierarchy root: doc_title / appendix (if any) / sections...
        doc_root = annex_pfx or result.source_document_title
        # Insert appendix as intermediate level in hierarchy
        if app_label:
            hier_root = f"{doc_root} / {app_label}"
        else:
            hier_root = doc_root
        if depth == 1:
            hierarchy = f"{hier_root} / {code} {title}".strip().rstrip("/").strip()
        else:
            parts_hier = [hier_root] + [f"{c} {t}".strip() for c, t in ancestor_stack]
            hierarchy = " / ".join(p for p in parts_hier if p)
        # Build unique ref_code: include appendix label to avoid collisions
        if app_label:
            ref_code = f"{annex_pfx} {app_label} § {code}" if annex_pfx else f"{app_label} § {code}"
        else:
            ref_code = f"{annex_pfx} § {code}" if annex_pfx else code
        # Deduplicate as last resort (shouldn't be needed with appendix key)
        if ref_code in seen_refs:
            seen_refs[ref_code] += 1
            ref_code = f"{ref_code} ({seen_refs[ref_code]})"
        else:
            seen_refs[ref_code] = 1
        full_title = f"{code} {title}".strip() if title else code

        h = hashlib.sha256(content.encode()).hexdigest()[:16]

        node = ParsedNode(
            node_type=node_type,  # type: ignore[arg-type]
            reference_code=ref_code,
            title=full_title,
            content_text=content,
            content_hash=h,
            hierarchy_path=hierarchy,
            regulatory_source=regulatory_source,
        )
        result.nodes.append(node)

        ancestor_stack.append((code, title))

    return result
