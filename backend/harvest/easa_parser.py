"""Parse the EASA Easy Access Rules Flat-OPC XML and produce regulatory nodes.

The file is a Word document in `pkg:package` form. Two parts matter:

  * `/customXml/item1.xml`   — a table of contents using the `er:` namespace.
    Each `<er:topic>` carries `sdt-id`, `source-title`, `ERulesId`, plus
    metadata such as `ApplicabilityDate`. `<er:heading>` elements delimit
    Annex / Section / Subpart boundaries in document order.
  * `/word/document.xml`     — the Word body. Each topic's content sits in a
    `<w:sdt>` block whose `w:sdtPr/w:id@w:val` matches the `sdt-id` from the
    TOC.

Phase 1 scope: Part 21 Annex I, Section A, Subparts B and D only (TCs and
changes to TCs). We keep all IR articles in that scope plus any AMC/GM/Appendix
topics whose title references an article in the scope.
"""
from __future__ import annotations

import hashlib
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from backend.harvest.easa_html_converter import HtmlConverter
from backend.harvest.models import NodeType, ParsedEdge, ParsedNode, ParseResult

PKG_NS = "http://schemas.microsoft.com/office/2006/xmlPackage"
ER_NS  = "http://www.easa.europa.eu/erules-export"
W_NS   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

# Robust regex for EASA article codes: 
# Supports "21.A.91", "M.A.101", "ARO.GEN.220(a)(1);(2)", "25J901", "25-11", etc.
# Pattern accepts: dotted (21.A.91), J-codes (25J901), hyphenated (25-11)
ARTICLE_CODE_PATTERN = r"[A-Z0-9]+(?:[\.-][A-Z0-9]+)*(?:\([a-z0-9-]+\))*(?:;(?:\([a-z0-9-]+\))*)*"

TITLE_RE = re.compile(
    r"""^\s*
    (?P<prefix>
        (?:Appendix\s+[A-Z0-9]+\s+to\s+)?        # "Appendix A to AMC ..."
        (?:(?:AMC|GM)\s*No\.?\s*\d*\s+to\s+)?    # "AMC No. 1 to CS ..." / "GM No 1 to ..."
        (?:AMC\s+to\s+)?                           # "AMC to CS ..."
        # Type prefix + optional spaced variant digit (only when followed by a letter-led code)
        # e.g. "AMC 1 ACNS.C.PBN.305" → prefix="AMC 1 ", code="ACNS.C.PBN.305"
        # but NOT "AMC 21.A.101" → should match prefix="AMC", code="21.A.101"
        (?:(?:AMC|GM)\s+\d+(?=\s+[A-Z])|AMC\d*|GM\d*|CS)?
        \s*
        (?:CS\s+)?                                 # optional "CS " between AMC/GM and the code
    )
    (?P<code>""" + ARTICLE_CODE_PATTERN + r""")               # the reference code
    (?:\s+(?P<title>.*))?$
    """,
    re.VERBOSE | re.UNICODE,
)

CROSSREF_RE = re.compile(ARTICLE_CODE_PATTERN)


# Subpart B  — Type Certificates          21.A.11  .. 21.A.55
# Subpart D  — Changes to TCs             21.A.90  .. 21.A.109
# Subpart E  — Supplemental TCs           21.A.111 .. 21.A.118B (num 111-118)
# Subpart G  — Production Organisation    21.A.131 .. 21.A.165
# Subpart J  — Design Organisation        21.A.231 .. 21.A.265
SUBPART_B_RANGE = range(11,  56)
SUBPART_D_RANGE = range(90,  110)
SUBPART_E_RANGE = range(111, 119)
SUBPART_G_RANGE = range(131, 166)
SUBPART_J_RANGE = range(231, 266)


@dataclass
class TopicRow:
    sdt_id: str
    title: str
    erules_id: str
    applicability_date: str | None
    entry_into_force_date: str | None
    regulatory_source: str | None
    type_of_content: str | None
    amended_by: str | None
    heading_stack: tuple[str, ...]


def _parse_package(
    xml_path: Path,
) -> tuple[etree._Element, etree._Element, dict[str, str]]:
    """Return (toc_root, doc_root, image_rid_map).

    image_rid_map maps relationship IDs (e.g. "rId5") to data-URI strings
    so that the HTML converter can inline images.
    """
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    toc_part: etree._Element | None = None
    doc_part: etree._Element | None = None
    rels_part: etree._Element | None = None
    image_parts: dict[str, tuple[str, str]] = {}  # path → (content_type, base64_data)

    for part in root.findall(f"{{{PKG_NS}}}part"):
        name = part.get(f"{{{PKG_NS}}}name") or ""
        ct = part.get(f"{{{PKG_NS}}}contentType") or ""
        xml_data = part.find(f"{{{PKG_NS}}}xmlData")
        
        if xml_data is None:
            continue

        # TOC detection: any part with a <document> element having a <toc>
        if "customXml" in name:
            tocs = xml_data.xpath(".//*[local-name()='toc']")
            if tocs:
                # Find the parent <document> or the root of this xmlData
                docs = xml_data.xpath(".//*[local-name()='document']")
                toc_part = docs[0] if docs else xml_data[0]
                continue
        
        # Document body detection: any part ending in document.xml having a <document>
        if name.endswith("/document.xml"):
            docs = xml_data.xpath(".//*[local-name()='document']")
            if docs:
                doc_part = docs[0]
                continue
            # Fallback to first element if no <document> found
            if len(xml_data) > 0:
                doc_part = xml_data[0]
        
        # Relationships
        elif name.endswith("/document.xml.rels"):
            rels_part = xml_data
            
        # Images
        elif "image" in ct.lower() or "/word/media/" in name:
            bd = part.find(f"{{{PKG_NS}}}binaryData")
            if bd is not None and bd.text:
                image_parts[name] = (ct, bd.text.strip())

    if toc_part is None or doc_part is None:
        raise RuntimeError("could not locate toc and document parts in the package")

    # Build rId → data-URI map
    image_rid_map: dict[str, str] = {}
    if rels_part is not None:
        for rel in rels_part.iter():
            if etree.QName(rel).localname != "Relationship":
                continue
            rid    = rel.get("Id") or ""
            target = rel.get("Target") or ""
            # Target is e.g. "media/image5.png"; the pkg:part name is "/word/media/image5.png"
            pkg_path = "/word/" + target if not target.startswith("/") else target
            if pkg_path in image_parts:
                ct, b64 = image_parts[pkg_path]
                # EMF images are not supported by browsers; skip them.
                if "emf" in ct.lower():
                    continue
                image_rid_map[rid] = f"data:{ct};base64,{b64}"

    return toc_part, doc_part, image_rid_map


def _heading_level(title: str) -> int:
    t = title.strip().upper().lstrip("(")
    if t.startswith("COVER"):
        return 0
    if t.startswith("ANNEX"):
        return 1
    if t.startswith("SUBPART"):
        return 2
    if t.startswith("SECTION"):
        return 3
    return 4


def _walk_toc(toc_element: etree._Element) -> list[TopicRow]:
    stack: list[str] = []
    rows: list[TopicRow] = []

    # Iterate over all elements within the TOC
    for el in toc_element.iter():
        tag = etree.QName(el).localname
        if tag == "heading":
            title = (el.get("title") or "").strip()
            level = _heading_level(title)
            stack[:] = stack[:level]
            while len(stack) < level:
                stack.append("")
            if stack:
                stack[-1] = title
            else:
                stack.append(title)
        elif tag == "topic":
            title = (el.get("source-title") or "").strip()
            if not title:
                continue
            rows.append(
                TopicRow(
                    sdt_id=el.get("sdt-id") or "",
                    title=title,
                    erules_id=el.get("ERulesId") or "",
                    applicability_date=el.get("ApplicabilityDate") or None,
                    entry_into_force_date=el.get("EntryIntoForceDate") or None,
                    regulatory_source=el.get("RegulatorySource") or None,
                    type_of_content=el.get("TypeOfContent") or None,
                    amended_by=el.get("AmendedBy") or None,
                    heading_stack=tuple(stack),
                )
            )
    return rows


def _build_sdt_index(doc_root: etree._Element) -> dict[str, etree._Element]:
    """Map SDT IDs → the innermost element that declares it, namespace-agnostic."""
    index: dict[str, etree._Element] = {}
    # Find all elements whose local name is 'sdt'
    for sdt in doc_root.xpath(".//*[local-name()='sdt']"):
        # Find the 'id' element within 'sdtPr'
        ids = sdt.xpath(".//*[local-name()='sdtPr']/*[local-name()='id']")
        if ids:
            # Get the 'val' attribute from any namespace
            val = ids[0].get(f"{{{W_NS}}}val") or ids[0].xpath("@*[local-name()='val']")
            if isinstance(val, list) and val:
                val = val[0]
            if val and val not in index:
                index[str(val)] = sdt
    return index


def _sdt_text(sdt: etree._Element) -> str:
    parts: list[str] = []
    for el in sdt.iter():
        tag = etree.QName(el).localname
        if tag == "t" and el.text:
            parts.append(el.text)
        elif tag in ("tab",):
            parts.append("\t")
        elif tag in ("br", "p", "cr"):
            parts.append("\n")
    text = "".join(parts)
    # Normalize whitespace: collapse interior runs, preserve newlines.
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _classify(title: str, default_node_type: NodeType = "IR") -> tuple[NodeType | None, str | None, str]:
    """Return (node_type, reference_code, cleaned_title) or (None, None, title).

    Pieces like ``AMC 21.A.91 Classification ...`` split into
    ``("AMC", "21.A.91", "Classification ...")``.
    
    Args:
        title: The topic title from the TOC
        default_node_type: Node type for bare codes ("IR" for Part 21, "CS" for CS-25/CS-ACNS)
    """
    # Fallback for standalone Appendix titles (no "to" clause)
    if title.strip().upper().startswith(("APPENDIX ", "APPENDIX\xa0")):
        # Try the main regex first
        m = TITLE_RE.match(title)
        if not m:
            # Standalone appendix: these are typically appendices to AMC, not CS articles.
            # Return "AMC" as the type; the caller may refine using TOC metadata.
            return "AMC", title.strip(), title.strip()
    else:
        m = TITLE_RE.match(title)
        if not m:
            return None, None, title
    
    prefix = (m.group("prefix") or "").strip().upper()
    code = m.group("code")
    tail = (m.group("title") or "").strip()

    # Extract variant number from prefix (AMC2, GM3, etc.)
    variant_num = ""
    if "APPENDIX" in prefix:
        # reference_code = "Appendix A to GM 21.A.101" (everything up to the article code)
        # title          = "Classification of design changes" (the tail after the code)
        idx = title.index(code)
        app_ref = title[:idx + len(code)].strip()
        node_title = tail or app_ref
        if "GM" in prefix:
            return "GM", app_ref, node_title
        if "AMC" in prefix:
            return "AMC", app_ref, node_title
        # Appendix with no AMC/GM in prefix: default to AMC (not CS)
        return "AMC", app_ref, node_title
    
    # Extract variant number (AMC2 → "2", GM3 → "3")
    if prefix.startswith("AMC"):
        variant_match = re.match(r"AMC\s*(\d+)", prefix)
        variant_num = variant_match.group(1) if variant_match else ""
        return "AMC", code, tail or title
    if prefix.startswith("GM"):
        variant_match = re.match(r"GM\s*(\d+)", prefix)
        variant_num = variant_match.group(1) if variant_match else ""
        return "GM", code, tail or title
    if prefix == "CS" or prefix.startswith("CS "):
        return "CS", code, tail or title
    if not prefix:
        return default_node_type, code, tail or title
    return None, code, title


def _in_scope(code: str) -> bool:
    """Check if the article code is within the desired scope.
    For now, we accept all codes matching the ARTICLE_CODE_PATTERN.
    """
    return True


def _hierarchy_path(stack: tuple[str, ...], doc_title: str = "") -> str:
    """Build hierarchy_path from structural headings only (no article code).
    Contract: parts[0]=root, parts[1]=subpart, parts[2]=section (optional).
    """
    parts = [seg for seg in stack if seg]
    # Deduplicate consecutive identical segments
    deduped: list[str] = []
    for seg in parts:
        if not deduped or deduped[-1] != seg:
            deduped.append(seg)
    parts = deduped
    # If no ANNEX-level heading anchors the root, prepend the document title
    # so all nodes from the same source share the same hierarchy root.
    # (CS-25, CS-AWO, CS-ACNS don't start with an Annex heading.)
    if doc_title and (not parts or _heading_level(parts[0]) > 1):
        parts = [doc_title] + parts
    return " / ".join(parts)


def _load_from_docx(
    docx_path: Path,
) -> tuple[etree._Element, etree._Element, dict[str, str]]:
    """Load toc_element, doc_root, and image_rid_map from an OOXML .docx file.

    A .docx is a ZIP that contains:
      - customXml/item*.xml  — one of these carries er:toc
      - word/document.xml    — the body with <w:sdt> blocks
      - word/_rels/document.xml.rels — image relationships
      - word/media/*         — image blobs
    """
    toc_element: etree._Element | None = None
    doc_root: etree._Element | None = None
    image_rid_map: dict[str, str] = {}

    with zipfile.ZipFile(docx_path) as zf:
        names = {f.filename for f in zf.infolist()}

        # 1. Find er:toc in customXml parts
        custom_xml_names = sorted(
            n for n in names if n.startswith("customXml/") and n.endswith(".xml")
        )
        for cx_name in custom_xml_names:
            with zf.open(cx_name) as fh:
                try:
                    cx_root = etree.parse(fh).getroot()
                except etree.XMLSyntaxError:
                    continue
                tocs = cx_root.xpath("//*[local-name()='toc']")
                if tocs:
                    docs = cx_root.xpath("//*[local-name()='document']")
                    toc_element = docs[0] if docs else cx_root
                    break

        # 2. Parse word/document.xml
        if "word/document.xml" in names:
            with zf.open("word/document.xml") as fh:
                doc_root = etree.parse(fh).getroot()

        # 3. Build rId → data-URI for images
        rels_name = "word/_rels/document.xml.rels"
        if rels_name in names:
            with zf.open(rels_name) as fh:
                try:
                    rels_root = etree.parse(fh).getroot()
                except etree.XMLSyntaxError:
                    rels_root = None
            if rels_root is not None:
                for rel in rels_root.iter():
                    if etree.QName(rel).localname != "Relationship":
                        continue
                    rid = rel.get("Id") or ""
                    target = rel.get("Target") or ""
                    media_name = "word/" + target if not target.startswith("/") else target.lstrip("/")
                    if media_name not in names:
                        continue
                    # Infer content-type from extension
                    ext = Path(target).suffix.lower().lstrip(".")
                    if ext == "emf":
                        continue
                    ct_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                              "gif": "image/gif", "svg": "image/svg+xml", "wmf": "image/wmf"}
                    ct = ct_map.get(ext, f"image/{ext}")
                    import base64
                    with zf.open(media_name) as img_fh:
                        b64 = base64.b64encode(img_fh.read()).decode()
                    image_rid_map[rid] = f"data:{ct};base64,{b64}"

    if toc_element is None:
        raise RuntimeError(f"er:toc not found in any customXml part of {docx_path}")
    if doc_root is None:
        raise RuntimeError(f"word/document.xml not found in {docx_path}")

    return toc_element, doc_root, image_rid_map


def _build_sdt_index_from_root(search_root: etree._Element) -> dict[str, etree._Element]:
    """Build sdt_id → sdt element index from any lxml element tree."""
    index: dict[str, etree._Element] = {}
    for sdt in search_root.xpath(".//*[local-name()='sdt']"):
        id_elements = sdt.xpath(".//*[local-name()='sdtPr']/*[local-name()='id']")
        if id_elements:
            id_el = id_elements[0]
            val = id_el.get(f"{{{W_NS}}}val") or id_el.get("val")
            if not val:
                attrs = id_el.xpath("@*[local-name()='val']")
                if attrs:
                    val = attrs[0]
            if val:
                index[str(val)] = sdt
    return index


def _build_image_rid_map_flatopc(root: etree._Element) -> dict[str, str]:
    """Build rId → data-URI map from a Flat-OPC pkg:package element.

    The Flat-OPC format embeds images as base64 in pkg:binaryData inside
    pkg:part elements. Relationships are stored in a separate pkg:part whose
    name ends with document.xml.rels.
    """
    import base64

    PKG = "http://schemas.microsoft.com/office/2006/xmlPackage"
    REL = "http://schemas.openxmlformats.org/package/2006/relationships"
    CT_MAP = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
              "gif": "image/gif", "svg": "image/svg+xml"}

    # Build name → base64 text for all media parts
    media_b64: dict[str, str] = {}
    for part in root.findall(f"{{{PKG}}}part"):
        name = part.get(f"{{{PKG}}}name") or ""
        if "/media/" not in name:
            continue
        bd = part.find(f"{{{PKG}}}binaryData")
        if bd is not None and bd.text:
            media_b64[name] = bd.text.strip()

    # Find the document.xml.rels part and build rId → media path
    rid_map: dict[str, str] = {}
    for part in root.findall(f"{{{PKG}}}part"):
        name = part.get(f"{{{PKG}}}name") or ""
        if not name.endswith("document.xml.rels"):
            continue
        xmlData = part.find(f"{{{PKG}}}xmlData")
        if xmlData is None:
            continue
        for rel in xmlData.iter():
            if etree.QName(rel).localname != "Relationship":
                continue
            rid    = rel.get("Id") or ""
            target = rel.get("Target") or ""
            if not rid or not target:
                continue
            ext = Path(target).suffix.lower().lstrip(".")
            if ext == "emf" or ext not in CT_MAP:
                continue
            # Normalise target to full package path
            full_name = f"/word/{target}" if not target.startswith("/") else target
            b64 = media_b64.get(full_name)
            if b64:
                ct = CT_MAP[ext]
                rid_map[rid] = f"data:{ct};base64,{b64}"
    return rid_map


def parse_easa_xml(xml_path: Path) -> ParseResult:
    # ── Format detection ────────────────────────────────────────────────────
    if xml_path.suffix.lower() == ".docx":
        toc_element, doc_root, image_rid_map = _load_from_docx(xml_path)
        source_title = ""
        parent = toc_element.getparent()
        if parent is not None:
            source_title = parent.get("source-title") or ""
        sdt_index = _build_sdt_index_from_root(doc_root)
    else:  # Flat-OPC pkg:package XML (Part 21 format)
        root = etree.parse(str(xml_path)).getroot()
        image_rid_map = _build_image_rid_map_flatopc(root)

        toc_elements = root.xpath("//*[local-name()='toc']")
        if not toc_elements:
            raise RuntimeError("er:toc not found in global search")
        toc_element = toc_elements[0]

        source_title = ""
        parent = toc_element.getparent()
        if parent is not None:
            source_title = parent.get("source-title") or ""

        # Build SDT index globally
        sdt_index: dict[str, etree._Element] = {}
        for sdt in root.xpath("//*[local-name()='sdt']"):
            id_elements = sdt.xpath(".//*[local-name()='sdtPr']/*[local-name()='id']")
            if id_elements:
                id_el = id_elements[0]
                val = id_el.get(f"{{{W_NS}}}val") or id_el.get("val")
                if not val:
                    attrs = id_el.xpath("@*[local-name()='val']")
                    if attrs:
                        val = attrs[0]
                if val:
                    sdt_index[str(val)] = sdt

    converter = HtmlConverter(image_rid_map)

    # Detect default node type: prefer er:document type-of-content attribute, fallback to title heuristic
    doc_type_of_content = ""
    try:
        doc_elements = toc_element.getparent()
        if doc_elements is not None:
            doc_type_of_content = (doc_elements.get("type-of-content") or "").upper()
    except Exception:
        pass
    if doc_type_of_content in ("CS",):
        default_node_type: NodeType = "CS"
    elif doc_type_of_content in ("IR", "AMC", "GM"):
        default_node_type: NodeType = "IR"
    else:
        # Fallback: title heuristic
        default_node_type = "CS" if source_title and re.search(r"\bCS[- ]", source_title) else "IR"

    rows = _walk_toc(toc_element)

    # Extract source_version: the highest-numbered Amendment/Revision/Issue across all topics.
    # "Initial issue" is skipped — it just means the article hasn't been amended since publication.
    from collections import Counter
    source_version: str | None = None
    best_num = -1
    best_label = None
    for r in rows:
        if not r.amended_by:
            continue
        for token in r.amended_by.split(";"):
            token = token.strip()
            vm = re.search(r"(Amendment|Revision|Issue)\s+(\d+)", token, re.IGNORECASE)
            if vm:
                n = int(vm.group(2))
                if n > best_num:
                    best_num = n
                    best_label = f"{vm.group(1).capitalize()} {n}"
    source_version = best_label
    # Fallback: document title
    if not source_version and source_title:
        vm = re.search(r"(?:Revision|Issue|Amendment)\s+\d+", source_title, re.IGNORECASE)
        if vm:
            source_version = vm.group(0)

    # Extract most recent EntryIntoForceDate for the document-level pub_time.
    # A single attribute may contain multiple semicolon-separated dates
    # e.g. "22 February, 2021; 22 February, 2023" — split all of them.
    from datetime import datetime as _dt
    all_date_tokens: list[str] = []
    for r in rows:
        if r.entry_into_force_date:
            for token in r.entry_into_force_date.split(";"):
                token = token.strip()
                if re.match(r"\d+ \w+, \d{4}", token):
                    all_date_tokens.append(token)
    source_pub_time: _dt | None = None
    if all_date_tokens:
        def _safe_parse(s: str) -> _dt:
            try:
                return _dt.strptime(s, "%d %B, %Y")
            except ValueError:
                return _dt.min
        latest_str = max(all_date_tokens, key=_safe_parse)
        parsed = _safe_parse(latest_str)
        if parsed != _dt.min:
            source_pub_time = parsed

    result = ParseResult(
        source_document_title=source_title,
        source_version=source_version,
        source_pub_time=source_pub_time,
    )

    nodes_by_ref: dict[tuple[str, str], ParsedNode] = {}

    for row in rows:
        node_type, code, clean_title = _classify(row.title, default_node_type)
        if node_type is None or code is None:
            continue

        # Override with TypeOfContent when _classify fell back to default (ambiguous bare code)
        if node_type == default_node_type and row.type_of_content:
            toc_val = row.type_of_content.upper()
            if toc_val == "AMC":
                node_type = "AMC"
            elif toc_val == "GM":
                node_type = "GM"
            elif toc_val == "IR":
                node_type = "IR"
            elif toc_val == "CS":
                node_type = "CS"

        # Refine standalone Appendix type using TOC metadata (type_of_content / heading_stack)
        # Only override if _classify didn't already resolve to AMC/GM (i.e. it fell back to default)
        if row.title.strip().upper().startswith(("APPENDIX ", "APPENDIX\xa0")) and node_type == default_node_type:
            toc = (row.type_of_content or "").upper()
            stack_str = " ".join(row.heading_stack).upper()
            if "GM" in toc or "GM" in stack_str:
                node_type = "GM"
            elif "AMC" in toc or "AMC" in stack_str:
                node_type = "AMC"
            else:
                # No signal — keep AMC as the safe default for appendices (not CS)
                node_type = "AMC"
        
        sdt = sdt_index.get(row.sdt_id)
        if sdt is None:
            continue
            
        text = _sdt_text(sdt)
        if not text:
            continue
            
        # Build reference_code: preserve variant numbers (AMC2, GM3) from original title
        reference_code = _build_reference_code(node_type, code, row.title)
        content_html = converter.sdt_to_html(sdt, title_to_skip=reference_code)
        content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()

        node = ParsedNode(
            node_type=node_type,
            reference_code=reference_code,
            title=clean_title,
            content_text=text,
            content_html=content_html,
            content_hash=content_hash,
            hierarchy_path=_hierarchy_path(row.heading_stack, doc_title=source_title),
            erules_id=row.erules_id,
            applicability_date=row.applicability_date,
            entry_into_force_date=row.entry_into_force_date,
            regulatory_source=row.regulatory_source,
        )
        key = (node_type, reference_code)
        if key not in nodes_by_ref:
            nodes_by_ref[key] = node
            result.nodes.append(node)

    # ── Second pass: encode parent article into standalone appendix reference_code ──────────────
    # Standalone appendices have reference_code like "Appendix 1 – title" with no "to AMC/CS".
    # We find the nearest preceding AMC/CS article in the same heading_stack and rewrite:
    #   "Appendix 1 – Assessment methods"  →  "Appendix 1 to AMC 25.1309 – Assessment methods"
    # This lets tree.ts articleCode() group them under their parent article without any
    # article codes in hierarchy_path.
    ref_to_node: dict[str, ParsedNode] = {n.reference_code: n for n in result.nodes}
    for i, row in enumerate(rows):
        if not row.title.strip().upper().startswith(("APPENDIX ", "APPENDIX\xa0")):
            continue
        if re.search(r"\bto\s+(?:AMC|GM|CS)\b", row.title, re.IGNORECASE):
            continue
        node_type_app, code_app, _ = _classify(row.title, default_node_type)
        if node_type_app is None:
            continue
        ref_code_app = _build_reference_code(node_type_app, code_app, row.title)
        app_node = ref_to_node.get(ref_code_app)
        if app_node is None:
            continue
        parent_ref: str | None = None
        for j in range(i - 1, -1, -1):
            prev = rows[j]
            if prev.heading_stack != row.heading_stack:
                continue
            if prev.title.strip().upper().startswith(("APPENDIX ", "APPENDIX\xa0")) and not re.search(r"\bto\s+(?:AMC|GM|CS)\b", prev.title, re.IGNORECASE):
                continue
            ptype, pcode, _ = _classify(prev.title, default_node_type)
            if ptype not in ("AMC", "GM", "CS", "IR"):
                continue
            if pcode and re.search(ARTICLE_CODE_PATTERN, pcode):
                if re.search(r"\b25[A-Z]\d|\b[A-Z]25\.", pcode):
                    continue
                parent_ref = _build_reference_code(ptype, pcode, prev.title)
                break
        if not parent_ref:
            continue
        # Rewrite reference_code to embed parent: "Appendix N – title" → "Appendix N to AMC 25.x – title"
        old_ref = app_node.reference_code
        m = re.match(r"^(Appendix\s+\S+)(.*)", old_ref, re.IGNORECASE)
        if m:
            app_node.reference_code = f"{m.group(1)} to {parent_ref}{m.group(2)}"
            ref_to_node.pop(old_ref, None)
            ref_to_node[app_node.reference_code] = app_node

    # ── Third pass: deduplicate CS appendices superseded by AMC in same batch ─────────────────
    # If an appendix node was classified as CS but an AMC exists for the same reference_code,
    # the CS version is spurious (standalone appendices are always AMC/GM, never CS articles).
    amc_refs = {n.reference_code for n in result.nodes if n.node_type in ("AMC", "GM") and re.match(r"^Appendix\b", n.reference_code, re.IGNORECASE)}
    result.nodes = [
        n for n in result.nodes
        if not (n.node_type == "CS" and re.match(r"^Appendix\b", n.reference_code, re.IGNORECASE) and n.reference_code in amc_refs)
    ]

    # Re-use existing edge logic...

    # Build edges: AMC/GM → IR or CS for the same article.
    # ir_refs covers both IR and CS node types (CS acts as the base article for CS docs).
    base_refs = {n.reference_code for n in result.nodes if n.node_type in ("IR", "CS")}
    for node in result.nodes:
        if node.node_type not in ("AMC", "GM"):
            continue
        # For "Appendix X to GM 21.A.101" — extract the article code after "to GM/AMC/CS"
        app_match = re.search(r"\bto\s+(?:AMC\d*|GM\d*|CS)\s+(" + ARTICLE_CODE_PATTERN + r")", node.reference_code, re.IGNORECASE)
        if app_match:
            stripped = app_match.group(1)
        else:
            # Strip the type prefix (AMC, AMC2, GM, GM3, etc.) to get the bare article code
            stripped = re.sub(r"^(?:AMC\d*|GM\d*)\s+", "", node.reference_code)
        m = re.search(ARTICLE_CODE_PATTERN, stripped)
        if not m:
            continue
        bare_code = m.group(0)
        # Strip sub-paragraph refs "(a)(2)" to find the parent article "25.1301"
        base_bare = re.sub(r"\([^)]*\).*$", "", bare_code).strip()
        # Try: exact bare, exact base, CS-prefixed bare, CS-prefixed base
        target = (
            bare_code if bare_code in base_refs
            else base_bare if base_bare in base_refs
            else f"CS {bare_code}" if f"CS {bare_code}" in base_refs
            else f"CS {base_bare}" if f"CS {base_bare}" in base_refs
            else None
        )
        if not target:
            continue
        relation = "ACCEPTABLE_MEANS" if node.node_type == "AMC" else "GUIDANCE_FOR"
        result.edges.append(
            ParsedEdge(source_ref=node.reference_code, target_ref=target, relation=relation)
        )

    # Cross-references inside base article text
    for node in result.nodes:
        if node.node_type not in ("IR", "CS"):
            continue
        for match in CROSSREF_RE.finditer(node.content_text):
            target = match.group(0)
            # Try bare code, then CS-prefixed
            resolved = (
                target if target in base_refs and target != node.reference_code
                else f"CS {target}" if f"CS {target}" in base_refs and f"CS {target}" != node.reference_code
                else None
            )
            if not resolved:
                continue
            result.edges.append(
                ParsedEdge(
                    source_ref=node.reference_code,
                    target_ref=resolved,
                    relation="REFERENCES",
                    confidence=0.80,
                    notes="auto-extracted from text",
                )
            )

    return result


def _prefix(node_type: NodeType) -> str:
    return {"IR": "", "AMC": "AMC ", "GM": "GM ", "CS": "CS "}[node_type]


def _build_reference_code(node_type: NodeType, code: str, original_title: str) -> str:
    """Build reference_code preserving variant numbers (AMC2, GM3) from the original title.
    
    Args:
        node_type: The classified node type
        code: The extracted article code
        original_title: The original TOC title to extract variant from
    
    Returns:
        Complete reference code like "AMC2 25.101" or "CS 25J901"
    """
    # If code already contains the full reference (Appendix), return as-is
    if "Appendix" in code:
        return code
    
    # Extract variant number from original title for AMC/GM
    variant = ""
    if node_type in ("AMC", "GM"):
        # Try "AMC No. X" or "AMC No X" format first
        no_match = re.search(rf"\b{node_type}\s+No\.?\s*(\d+)\b", original_title, re.IGNORECASE)
        if no_match:
            variant = no_match.group(1)
        else:
            # Try "AMC2", "AMC 2", "GM3", "GM 3", etc.
            # The variant number must be followed by a space or end-of-token (not a dot),
            # e.g. "AMC2 ACNS..." or "AMC 2 CS..." but NOT "AMC 25.1301" (25 is the article)
            variant_match = re.search(
                rf"\b{node_type}\s*(\d+)(?=\s|$)(?!\s*\.)",
                original_title, re.IGNORECASE
            )
            if variant_match:
                variant = variant_match.group(1)
    
    # Build the reference code
    prefix = _prefix(node_type)
    if variant:
        # Insert variant number right after the type: "AMC2 25.101"
        return f"{node_type}{variant} {code}".strip()
    else:
        # Standard format: "AMC 25.101" or "CS 25.101" or bare code for IR
        return f"{prefix}{code}".strip()
