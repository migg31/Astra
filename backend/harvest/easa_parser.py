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
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from backend.harvest.easa_html_converter import HtmlConverter
from backend.harvest.models import NodeType, ParsedEdge, ParsedNode, ParseResult

PKG_NS = "http://schemas.microsoft.com/office/2006/xmlPackage"
ER_NS  = "http://www.easa.europa.eu/erules-export"
W_NS   = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

# Titles look like:
#   "21.A.91 Classification of changes to a type certificate"
#   "AMC 21.A.91 Classification of changes ..."
#   "GM 21.A.91 Classification of changes ..."
#   "GM1 21.A.91 ..."    (newer style, numbered)
#   "Appendix A to GM 21.A.91 Examples ..."
#   "Appendix I to 21.A.91 ..."
TITLE_RE = re.compile(
    r"""^\s*
    (?P<prefix>
        (?:Appendix\s+[A-Z0-9]+\s+to\s+)?
        (?:AMC\d*|GM\d*|CS)?                 # optional type prefix
        \s*
    )
    (?P<code>21\.A\.\d+[A-Z]?)               # the reference code
    (?:\s+(?P<title>.*))?$
    """,
    re.VERBOSE,
)

CROSSREF_RE = re.compile(r"21\.A\.\d+[A-Z]?")

# Subpart B (TCs) is 21.A.11..55; Subpart D (changes) is 21.A.90..109.
SUBPART_B_RANGE = range(11, 56)
SUBPART_D_RANGE = range(90, 110)


@dataclass
class TopicRow:
    sdt_id: str
    title: str
    erules_id: str
    applicability_date: str | None
    entry_into_force_date: str | None
    regulatory_source: str | None
    type_of_content: str | None
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
        if name == "/customXml/item1.xml":
            toc_part = part.find(f"{{{PKG_NS}}}xmlData/{{{ER_NS}}}document")
        elif name == "/word/document.xml":
            doc_part = part.find(f"{{{PKG_NS}}}xmlData/{{{W_NS}}}document")
        elif name == "/word/_rels/document.xml.rels":
            rels_part = part.find(f"{{{PKG_NS}}}xmlData")
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
    if t.startswith("SECTION"):
        return 2
    if t.startswith("SUBPART"):
        return 3
    return 4


def _walk_toc(toc_root: etree._Element) -> list[TopicRow]:
    stack: list[str] = []
    rows: list[TopicRow] = []
    toc = toc_root.find(f"{{{ER_NS}}}toc")
    if toc is None:
        raise RuntimeError("er:toc not found")

    for el in toc.iter():
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
                    heading_stack=tuple(stack),
                )
            )
    return rows


def _build_sdt_index(doc_root: etree._Element) -> dict[str, etree._Element]:
    """Map `w:id@w:val` → the innermost `<w:sdt>` element that declares it."""
    index: dict[str, etree._Element] = {}
    for sdt in doc_root.iter(f"{{{W_NS}}}sdt"):
        id_el = sdt.find(f"{{{W_NS}}}sdtPr/{{{W_NS}}}id")
        if id_el is None:
            continue
        val = id_el.get(f"{{{W_NS}}}val")
        if val and val not in index:
            index[val] = sdt
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


def _classify(title: str) -> tuple[NodeType | None, str | None, str]:
    """Return (node_type, reference_code, cleaned_title) or (None, None, title).

    Pieces like ``AMC 21.A.91 Classification ...`` split into
    ``("AMC", "21.A.91", "Classification ...")``.
    """
    m = TITLE_RE.match(title)
    if not m:
        return None, None, title
    prefix = (m.group("prefix") or "").strip().upper()
    code = m.group("code")
    tail = (m.group("title") or "").strip()

    if "APPENDIX" in prefix:
        # Appendix to a GM or AMC — classify under the same family.
        if "GM" in prefix:
            return "GM", code, title
        if "AMC" in prefix:
            return "AMC", code, title
        # "Appendix I to 21.A.XX" — treat as IR annex.
        return "IR", code, title
    if prefix.startswith("AMC"):
        return "AMC", code, tail or title
    if prefix.startswith("GM"):
        return "GM", code, tail or title
    if not prefix:
        return "IR", code, tail or title
    return None, code, title


def _in_scope(code: str) -> bool:
    m = re.match(r"^21\.A\.(\d+)", code)
    if not m:
        return False
    num = int(m.group(1))
    return num in SUBPART_B_RANGE or num in SUBPART_D_RANGE


def _hierarchy_path(code: str, stack: tuple[str, ...]) -> str:
    parts = [seg for seg in stack if seg]
    parts.append(code)
    return " / ".join(parts)


def parse_easa_xml(xml_path: Path) -> ParseResult:
    toc_root, doc_root, image_rid_map = _parse_package(xml_path)
    converter = HtmlConverter(image_rid_map)
    pub_time_attr = toc_root.get("pub-time")
    source_title = toc_root.get("source-title") or ""

    rows = _walk_toc(toc_root)
    sdt_index = _build_sdt_index(doc_root)

    result = ParseResult(
        source_document_title=source_title,
        source_pub_time=None,  # set below from attr if parseable
    )
    if pub_time_attr:
        try:
            from datetime import datetime as _dt

            result.source_pub_time = _dt.fromisoformat(pub_time_attr.replace("Z", "+00:00"))
        except ValueError:
            pass

    nodes_by_ref: dict[tuple[str, str], ParsedNode] = {}

    for row in rows:
        node_type, code, clean_title = _classify(row.title)
        if node_type is None or code is None:
            continue
        if not _in_scope(code):
            continue
        sdt = sdt_index.get(row.sdt_id)
        if sdt is None:
            continue
        text = _sdt_text(sdt)
        if not text:
            continue
        content_html = converter.sdt_to_html(sdt)
        content_hash = hashlib.md5(text.encode("utf-8")).hexdigest()  # noqa: S324
        reference_code = row.title if "Appendix" in row.title else f"{_prefix(node_type)}{code}".strip()

        node = ParsedNode(
            node_type=node_type,
            reference_code=reference_code,
            title=clean_title,
            content_text=text,
            content_html=content_html,
            content_hash=content_hash,
            hierarchy_path=_hierarchy_path(reference_code, row.heading_stack),
            erules_id=row.erules_id,
            applicability_date=row.applicability_date,
            entry_into_force_date=row.entry_into_force_date,
            regulatory_source=row.regulatory_source,
        )
        key = (node_type, reference_code)
        if key in nodes_by_ref:
            continue  # skip duplicates (the first SDT wins)
        nodes_by_ref[key] = node
        result.nodes.append(node)

    # Build edges: AMC/GM → IR for same article.
    ir_refs = {n.reference_code for n in result.nodes if n.node_type == "IR"}
    for node in result.nodes:
        if node.node_type not in ("AMC", "GM"):
            continue
        # extract the 21.A.XX present in the reference_code
        m = re.search(r"21\.A\.\d+[A-Z]?", node.reference_code)
        if not m:
            continue
        target_ir = m.group(0)
        if target_ir not in ir_refs:
            continue
        if node.node_type == "AMC":
            relation = "ACCEPTABLE_MEANS"
        else:
            relation = "GUIDANCE_FOR"
        result.edges.append(
            ParsedEdge(
                source_ref=node.reference_code,
                target_ref=target_ir,
                relation=relation,
            )
        )

    # Cross-references inside IR text: every 21.A.XX not equal to the node's
    # own reference becomes a REFERENCES edge with confidence 0.80.
    for node in result.nodes:
        if node.node_type != "IR":
            continue
        for match in CROSSREF_RE.finditer(node.content_text):
            target = match.group(0)
            if target == node.reference_code:
                continue
            if target not in ir_refs:
                continue
            result.edges.append(
                ParsedEdge(
                    source_ref=node.reference_code,
                    target_ref=target,
                    relation="REFERENCES",
                    confidence=0.80,
                    notes="auto-extracted from IR text",
                )
            )

    return result


def _prefix(node_type: NodeType) -> str:
    return {"IR": "", "AMC": "AMC ", "GM": "GM ", "CS": "CS "}[node_type]
