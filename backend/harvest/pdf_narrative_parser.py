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
    r"^(AMC\s*\d+\s*$|Page\s+\d+\s+of\s+\d+|Powered by EASA|©\s*\d{4}|Annex\s+(I|II|III|IV|V|VI|VII))", re.IGNORECASE
)
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
                txt = span["text"]
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
            line_text = " ".join(t for t, _, _ in merged).strip()
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
    all_lines: list[_Line] = []
    for page in doc:
        for ln in _extract_lines(page):
            txt = ln.text.strip()
            if not txt:
                continue
            if _PAGE_FOOTER_RE.match(txt):
                continue
            if _TOC_DOT_RE.search(txt):
                continue
            all_lines.append(ln)

    # ── Pass 2: segment into sections ────────────────────────────────────
    # Each section: (code, title, body_lines)
    sections: list[tuple[str, str, list[str]]] = []
    current_code: str | None = None
    current_title: str = ""
    current_body: list[str] = []

    for ln in all_lines:
        m = _is_heading(ln)
        if m:
            code = m.group(1)
            heading_rest = (m.group(2) or "").strip()
            if current_code is not None:
                sections.append((current_code, current_title, current_body))
            # Accumulate multi-word headings that follow on next bold lines
            current_code = code
            current_title = heading_rest
            current_body = []
        else:
            if current_code is None:
                continue  # preamble before first section
            # If previous section had no title yet and this line is bold → title continuation
            if not current_title and ln.bold:
                current_title = ln.text.strip()
            else:
                current_body.append(ln.text.strip())

    if current_code is not None:
        sections.append((current_code, current_title, current_body))

    if not sections:
        return result

    # ── Pass 3: build hierarchy and ParsedNodes ──────────────────────────
    # Stack of (code, title) for ancestors
    ancestor_stack: list[tuple[str, str]] = []

    for code, title, body_lines in sections:
        depth = _section_depth(code)

        # Skip TOC ghost entries (no title and no body)
        content = "\n".join(body_lines).strip()
        if not title and not content:
            continue

        # Trim ancestor stack to current depth
        while len(ancestor_stack) >= depth:
            ancestor_stack.pop()

        hierarchy = _hierarchy_path(result.source_document_title, ancestor_stack)
        ref_code = f"{regulatory_source} § {code}".strip(" §") if regulatory_source else code
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
