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
    # EASA IR styles
    "heading2ir": "h2", "heading3ir": "h3", "heading4ir": "h4",
    # EASA AMC styles
    "heading4amc": "h3", "heading5amc": "h4", "heading6amc": "h5", "heading7amc": "h6",
    # EASA GM styles
    "heading2gm": "h3", "heading3gm": "h4", "heading4gm": "h5", "heading5gm": "h6", "heading6gm": "h6",
    # EASA CS styles
    "heading3cs": "h4", "heading4cs": "h5", "heading5cs": "h6",
    # Org manual / other heading variants
    "heading3orgmanual": "h4", "heading4orgmanual": "h5",
    "heading5orgmanual": "h5", "heading6orgmanual": "h6",
    # Titles
    "title": "h1", "easaheadertitle": "h1",
    # legacy/fallback
    "ruletitle": "h2", "amctitle": "h3", "gmtitle": "h3",
}

# Styles that map to list items
LIST_STYLES = {
    "listparagraph", "list paragraph", "listbullet", "list bullet",
    "listnumber", "list number", "listcontinue",
    # EASA numeric indent levels (treated as ordered list items)
    "listlevel0", "listlevel1", "listlevel2", "listlevel3", "listlevel4", "listlevel5",
    # EASA bullet styles
    "bullet0", "bullet1", "bullet2", "bullet3", "bullet4",
}

# Styles that are rendered as smaller/secondary text
SMALL_STYLES = {"fineprint", "footnotetext", "footer"}

# Styles to suppress entirely (TOC, internal Word metadata)
SUPPRESS_STYLES = {
    "toc1", "toc2", "toc3", "toc4", "toc5", "toc6", "toc7", "toc8", "toc9",
    "tableofcontents", "tocheading",
}

EASA_BLOCK_TYPES = {
    "heading2ir": "easa-rule",   "heading3ir": "easa-rule",   "heading4ir": "easa-rule",
    "heading4amc": "easa-amc",  "heading5amc": "easa-amc",  "heading6amc": "easa-amc",
    "heading2gm": "easa-gm",    "heading3gm": "easa-gm",    "heading4gm": "easa-gm",
    "heading5gm": "easa-gm",    "heading6gm": "easa-gm",
    "heading3cs": "easa-rule",  "heading4cs": "easa-rule",  "heading5cs": "easa-rule",
    "amctitle": "easa-amc",     "gmtitle": "easa-gm",       "ruletitle": "easa-rule",
}


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

    def sdt_to_html(self, sdt: etree._Element, title_to_skip: str | None = None) -> str:
        # The sdtContent element holds the actual content.
        content = sdt.find(f"{{{W}}}sdtContent")
        if content is None:
            content = sdt

        # Flatten nested SDTs to process a linear sequence of paragraphs and tables.
        elements = self._flatten_elements(content)

        parts = []
        current_block = None
        skipped_title = False
        current_list_type: str | None = None  # "ul" or "ol"

        def _close_list():
            nonlocal current_list_type
            if current_list_type:
                parts.append(f"</{current_list_type}>\n")
                current_list_type = None

        for el in elements:
            t = _tag(el)
            style = ""
            if t == "p":
                style = self._get_style(el)

            block_type = self._get_block_type(style)
            is_major_heading = style in ("heading1", "heading2", "chaptertitle")

            if block_type or is_major_heading:
                _close_list()
                if current_block:
                    parts.append("</div>\n")
                    current_block = None
                if block_type:
                    parts.append(f'<div class="easa-block {block_type}">\n')
                    current_block = block_type

            if t == "p":
                if not skipped_title and title_to_skip:
                    text = "".join(node.text for node in el.iter(f"{{{W}}}t") if node.text).strip()
                    if text and (text in title_to_skip or title_to_skip in text):
                        skipped_title = True
                        continue

                if self._get_style(el) == "regulatorysource":
                    continue

                html = self._para(el)
                if html:
                    # Group consecutive <li> into <ul>/<ol>
                    m = re.match(r'<li data-list="(ul|ol)"', html)
                    if m:
                        lt = m.group(1)
                        if current_list_type != lt:
                            _close_list()
                            parts.append(f"<{lt}>\n")
                            current_list_type = lt
                        # Strip data-list attribute before appending
                        html = re.sub(r' data-list="(?:ul|ol)"', "", html, count=1)
                    else:
                        _close_list()
                    parts.append(html)
            elif t == "tbl":
                _close_list()
                parts.append(self._table(el))

        _close_list()
        if current_block:
            parts.append("</div>\n")

        return "".join(parts)

    def _get_block_type(self, style: str) -> str | None:
        s = style.lower()
        if "amc" in s: return "easa-amc"
        if "gm" in s:  return "easa-gm"
        if "ir" in s or "rule" in s: return "easa-rule"
        return None

    def _flatten_elements(self, container: etree._Element) -> list[etree._Element]:
        """Recursively collect paragraphs and tables, flattening nested SDTs."""
        flat = []
        for child in container:
            t = _tag(child)
            if t == "sdt":
                content = child.find(f"{{{W}}}sdtContent")
                if content is not None:
                    flat.extend(self._flatten_elements(content))
            elif t in ("p", "tbl"):
                flat.append(child)
        return flat

    def _get_style(self, p: etree._Element) -> str:
        pPr = p.find(f"{{{W}}}pPr")
        if pPr is not None:
            pStyle = pPr.find(f"{{{W}}}pStyle")
            if pStyle is not None:
                return (_attr(pStyle, W, "val") or "").lower().replace(" ", "")
        return ""

    # ------------------------------------------------------------------
    # Paragraph
    # ------------------------------------------------------------------

    def _para(self, p: etree._Element) -> str:
        pPr = p.find(f"{{{W}}}pPr")
        style = ""
        numPr = None
        indent_style = ""
        p_bold = p_italic = p_underline = False
        is_bullet = False
        is_center = False
        if pPr is not None:
            pStyle = pPr.find(f"{{{W}}}pStyle")
            if pStyle is not None:
                style = (_attr(pStyle, W, "val") or "").lower().replace(" ", "")
            numPr = pPr.find(f"{{{W}}}numPr")

            # Detect bullet vs numbered list
            if numPr is not None:
                fmt_el = numPr.find(f"{{{W}}}numFmt")
                fmt_val = _attr(fmt_el, W, "val") if fmt_el is not None else None
                is_bullet = fmt_val in ("bullet", None) and ("listbullet" in style or "bullet" in style)

            # Extract indentation (w:ind)
            ind = pPr.find(f"{{{W}}}ind")
            if ind is not None:
                left = _attr(ind, W, "left")
                if left and left.isdigit():
                    rem = int(left) / 240.0
                    if rem > 0:
                        indent_style = f'padding-left: {rem:.2f}rem;'

            # Text alignment
            jc = pPr.find(f"{{{W}}}jc")
            if jc is not None and _attr(jc, W, "val") == "center":
                is_center = True

            # Paragraph-level formatting
            rPr = pPr.find(f"{{{W}}}rPr")
            if rPr is not None:
                p_bold = rPr.find(f"{{{W}}}b") is not None
                p_italic = rPr.find(f"{{{W}}}i") is not None
                p_underline = rPr.find(f"{{{W}}}u") is not None

        inline = self._inline_content(p)
        if not inline.strip():
            return ""

        if p_bold:      inline = f"<strong>{inline}</strong>"
        if p_italic:    inline = f"<em>{inline}</em>"
        if p_underline: inline = f"<u>{inline}</u>"

        tag = HEADING_STYLES.get(style, None)
        if tag and tag.startswith("h"):
            style_parts = []
            if indent_style: style_parts.append(indent_style)
            if is_center:    style_parts.append("text-align:center;")
            style_attr = f' style="{" ".join(style_parts)}"' if style_parts else ""
            return f'<{tag}{style_attr}>{inline}</{tag}>\n'

        # Suppress TOC and other unwanted styles entirely
        if style in SUPPRESS_STYLES:
            return ""

        css_classes = []
        if style == "regulatorysource":  css_classes.append("reg-source")
        if "dxshortdesc" in style:       css_classes.append("reg-decision")
        if style in SMALL_STYLES:        css_classes.append("easa-fineprint")

        style_parts = []
        if indent_style: style_parts.append(indent_style)
        if is_center:    style_parts.append("text-align:center;")

        css_class_attr = f' class="{" ".join(css_classes)}"' if css_classes else ""
        final_style = f' style="{" ".join(style_parts)}"' if style_parts else ""

        # Bullet styles → ul, everything else with numPr or list style → ol
        is_bullet_style = any(s in style for s in ("bullet",))
        if style in LIST_STYLES or numPr is not None:
            list_type = "ul" if (is_bullet or is_bullet_style) else "ol"
            return f"<li data-list=\"{list_type}\"{css_class_attr}{final_style}>{inline}</li>\n"

        return f"<p{css_class_attr}{final_style}>{inline}</p>\n"

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

    # Named character styles → formatting inference
    _RSTYLE_BOLD   = {"strong", "bold"}
    _RSTYLE_ITALIC = {"emphasis", "italic", "book title", "booktitle",
                      "intensereference", "intense reference"}

    def _run(self, r: etree._Element) -> str:
        rPr = r.find(f"{{{W}}}rPr")
        bold = italic = underline = strike = caps = superscript = subscript = False
        color: str | None = None
        if rPr is not None:
            bold      = rPr.find(f"{{{W}}}b")      is not None
            italic    = rPr.find(f"{{{W}}}i")      is not None
            underline = rPr.find(f"{{{W}}}u")      is not None
            strike    = rPr.find(f"{{{W}}}strike") is not None
            caps      = rPr.find(f"{{{W}}}caps")   is not None
            # Named character style (rStyle) — infer formatting
            rStyle_el = rPr.find(f"{{{W}}}rStyle")
            if rStyle_el is not None:
                rs = (_attr(rStyle_el, W, "val") or "").lower().replace(" ", "")
                if rs in self._RSTYLE_BOLD:   bold   = True
                if rs in self._RSTYLE_ITALIC: italic = True
            # Color
            color_el = rPr.find(f"{{{W}}}color")
            if color_el is not None:
                c = _attr(color_el, W, "val") or ""
                if c and c.lower() not in ("auto", "000000", "ffffff"):
                    color = f"#{c}"
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
        if caps:        text = text.upper()
        if bold:        text = f"<strong>{text}</strong>"
        if italic:      text = f"<em>{text}</em>"
        if underline:   text = f"<u>{text}</u>"
        if strike:      text = f"<s>{text}</s>"
        if color:       text = f'<span style="color:{color}">{text}</span>'
        return text

    def _hyperlink(self, hl: etree._Element) -> str:
        # We don't resolve external hyperlinks for safety; just render the text.
        # Recurse into nested hyperlinks (EASA cross-references are often doubly-wrapped).
        inner = ""
        for child in hl:
            t = _tag(child)
            if t == "r":
                inner += self._run(child)
            elif t == "hyperlink":
                inner += self._hyperlink(child)
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
