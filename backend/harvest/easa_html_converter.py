"""Convert a Word SDT element to clean HTML.

Handles the structures found in EASA Easy Access Rules:
  - paragraphs with heading / list / normal styles
  - inline formatting: bold, italic, underline, superscript/subscript
  - Word tables (<w:tbl>)
  - hyperlinks (<w:hyperlink>)
  - drawings/images (resolved from the document relationship map to data-URIs)
  - tab characters, non-breaking hyphens

Images are embedded inline as data-URIs. For a PoC with a handful of
images this is acceptable; at scale they should be stored separately.
"""
from __future__ import annotations

import re
from lxml import etree

W  = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A  = "http://schemas.openxmlformats.org/drawingml/2006/main"
WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
PIC = "http://schemas.openxmlformats.org/drawingml/2006/picture"
R   = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

# Word paragraph style name → HTML element
HEADING_STYLES = {
    "heading1": "h2", "heading2": "h3", "heading3": "h4",
    "heading4": "h5", "heading5": "h6",
    # EASA-specific style names observed in the document
    "ruletitle": "h2", "amctitle": "h3", "gmtitle": "h3",
    "chaptertitle": "h2", "sectiontitle": "h3",
    "regulatorysource": "p",  # treated as plain, styled via CSS class
}
LIST_STYLES = {"listparagraph", "list paragraph", "listbullet", "list bullet",
               "listnumber", "list number", "listcontinue"}


def _tag(el: etree._Element) -> str:
    return etree.QName(el).localname


def _attr(el: etree._Element, ns: str, name: str) -> str | None:
    return el.get(f"{{{ns}}}{name}")


def _escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))


class HtmlConverter:
    """Stateful converter; create one per SDT."""

    def __init__(self, image_rid_map: dict[str, str]) -> None:
        """
        image_rid_map: maps relationship ID (e.g. "rId5") →
                       data-URI string ("data:image/png;base64,...")
        """
        self._images = image_rid_map

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def sdt_to_html(self, sdt: etree._Element) -> str:
        # The sdtContent element holds the actual content.
        content = sdt.find(f"{{{W}}}sdtContent")
        if content is None:
            content = sdt
        parts = []
        for child in content:
            t = _tag(child)
            if t == "p":
                parts.append(self._para(child))
            elif t == "tbl":
                parts.append(self._table(child))
            elif t == "sdt":
                # Nested SDT — recurse
                parts.append(self.sdt_to_html(child))
        return "".join(p for p in parts if p)

    # ------------------------------------------------------------------
    # Paragraph
    # ------------------------------------------------------------------

    def _para(self, p: etree._Element) -> str:
        pPr = p.find(f"{{{W}}}pPr")
        style = ""
        numPr = None
        if pPr is not None:
            pStyle = pPr.find(f"{{{W}}}pStyle")
            if pStyle is not None:
                style = (_attr(pStyle, W, "val") or "").lower().replace(" ", "")
            numPr = pPr.find(f"{{{W}}}numPr")

        inline = self._inline_content(p)
        if not inline.strip():
            return ""

        tag = HEADING_STYLES.get(style, None)
        if tag and tag.startswith("h"):
            return f"<{tag}>{inline}</{tag}>\n"

        css_class = ""
        if style == "regulatorysource":
            css_class = ' class="reg-source"'
        elif style in LIST_STYLES or numPr is not None:
            # We emit a plain <li>; the caller wraps in <ul>/<ol> if needed.
            return f"<li>{inline}</li>\n"

        return f"<p{css_class}>{inline}</p>\n"

    # ------------------------------------------------------------------
    # Inline content (runs, hyperlinks, drawings within a paragraph)
    # ------------------------------------------------------------------

    def _inline_content(self, parent: etree._Element) -> str:
        parts: list[str] = []
        for child in parent:
            t = _tag(child)
            if t == "r":
                parts.append(self._run(child))
            elif t == "hyperlink":
                parts.append(self._hyperlink(child))
            elif t == "drawing":
                parts.append(self._drawing(child))
            elif t == "pPr":
                pass  # already handled above
            elif t in ("bookmarkStart", "bookmarkEnd", "proofErr",
                       "rPrChange", "pPrChange"):
                pass
        return "".join(parts)

    def _run(self, r: etree._Element) -> str:
        rPr = r.find(f"{{{W}}}rPr")
        bold = italic = underline = superscript = subscript = False
        if rPr is not None:
            bold      = rPr.find(f"{{{W}}}b")    is not None
            italic    = rPr.find(f"{{{W}}}i")    is not None
            underline = rPr.find(f"{{{W}}}u")    is not None
            va = rPr.find(f"{{{W}}}vertAlign")
            if va is not None:
                val = _attr(va, W, "val") or ""
                superscript = val == "superscript"
                subscript   = val == "subscript"

        parts: list[str] = []
        for child in r:
            t = _tag(child)
            if t == "t":
                parts.append(_escape(child.text or ""))
            elif t == "tab":
                parts.append("&emsp;")
            elif t == "br":
                parts.append("<br>")
            elif t == "noBreakHyphen":
                parts.append("\u2011")  # non-breaking hyphen
            elif t == "drawing":
                parts.append(self._drawing(child))

        text = "".join(parts)
        if not text:
            return ""

        if superscript: text = f"<sup>{text}</sup>"
        if subscript:   text = f"<sub>{text}</sub>"
        if bold:        text = f"<strong>{text}</strong>"
        if italic:      text = f"<em>{text}</em>"
        if underline:   text = f"<u>{text}</u>"
        return text

    def _hyperlink(self, hl: etree._Element) -> str:
        rid = _attr(hl, R, "id")
        # We don't resolve external hyperlinks for safety; just render the text.
        inner = ""
        for child in hl:
            t = _tag(child)
            if t == "r":
                inner += self._run(child)
        return inner

    # ------------------------------------------------------------------
    # Drawing / image
    # ------------------------------------------------------------------

    def _drawing(self, drawing: etree._Element) -> str:
        # Walk to <a:blip r:embed="rIdXX">
        for blip in drawing.iter(f"{{{A}}}blip"):
            rid = _attr(blip, R, "embed")
            if rid and rid in self._images:
                data_uri = self._images[rid]
                return f'<img src="{data_uri}" class="doc-image" alt="diagram">\n'
        return '<span class="doc-image-missing">[diagram]</span>'

    # ------------------------------------------------------------------
    # Table  (handles colspan, rowspan, header rows)
    # ------------------------------------------------------------------

    def _tc_props(self, tc: etree._Element) -> tuple[int, str]:
        """Return (colspan, vmerge_type) for a <w:tc> element.

        vmerge_type is one of: "normal" | "restart" | "continue"
        """
        colspan = 1
        vmerge = "normal"
        tcPr = tc.find(f"{{{W}}}tcPr")
        if tcPr is not None:
            gs = tcPr.find(f"{{{W}}}gridSpan")
            if gs is not None:
                colspan = int(gs.get(f"{{{W}}}val") or 1)
            vm = tcPr.find(f"{{{W}}}vMerge")
            if vm is not None:
                vmerge = "restart" if vm.get(f"{{{W}}}val") == "restart" else "continue"
        return colspan, vmerge

    def _row_col_map(self, tr: etree._Element) -> dict[int, tuple[str, int]]:
        """Map each grid column index → (vmerge_type, colspan) for the given row."""
        result: dict[int, tuple[str, int]] = {}
        col = 0
        for tc in tr.findall(f"{{{W}}}tc"):
            colspan, vmerge = self._tc_props(tc)
            for c in range(col, col + colspan):
                result[c] = (vmerge, colspan)
            col += colspan
        return result

    def _rowspan_for(self, rows: list, ri: int, col: int) -> int:
        """Count how many rows the restart cell at (ri, col) spans."""
        span = 1
        for future_ri in range(ri + 1, len(rows)):
            col_map = self._row_col_map(rows[future_ri])
            if col_map.get(col, ("normal", 1))[0] == "continue":
                span += 1
            else:
                break
        return span

    def _cell_html(self, tc: etree._Element, tag: str, colspan: int, rowspan: int) -> str:
        attrs = ""
        if colspan > 1:
            attrs += f' colspan="{colspan}"'
        if rowspan > 1:
            attrs += f' rowspan="{rowspan}"'
        content_parts: list[str] = []
        for child in tc:
            t = _tag(child)
            if t == "p":
                content_parts.append(self._para(child))
            elif t == "tbl":
                content_parts.append(self._table(child))
        raw = "".join(content_parts).strip()
        # Unwrap a single <p>…</p> wrapping
        m = re.match(r"^<p(?:\s[^>]*)?>(.+?)</p>$", raw, re.DOTALL)
        content = m.group(1) if m and raw.count("</p>") == 1 else raw
        return f"<{tag}{attrs}>{content}</{tag}>"

    def _table(self, tbl: etree._Element) -> str:
        rows = tbl.findall(f"{{{W}}}tr")
        html_rows: list[str] = []

        for ri, tr in enumerate(rows):
            trPr = tr.find(f"{{{W}}}trPr")
            is_hdr = trPr is not None and trPr.find(f"{{{W}}}tblHeader") is not None
            cell_tag = "th" if is_hdr else "td"

            cells_html: list[str] = []
            col = 0
            for tc in tr.findall(f"{{{W}}}tc"):
                colspan, vmerge = self._tc_props(tc)
                if vmerge == "continue":
                    col += colspan
                    continue  # merged vertically from above — omit
                rowspan = (
                    self._rowspan_for(rows, ri, col)
                    if vmerge == "restart"
                    else 1
                )
                cells_html.append(self._cell_html(tc, cell_tag, colspan, rowspan))
                col += colspan

            if cells_html:
                html_rows.append(f"  <tr>{''.join(cells_html)}</tr>\n")

        return f"<table>\n{''.join(html_rows)}</table>\n"
