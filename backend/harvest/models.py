from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

NodeType = Literal["IR", "AMC", "GM", "CS"]


@dataclass
class ParsedNode:
    node_type: NodeType
    reference_code: str
    title: str
    content_text: str
    content_hash: str
    hierarchy_path: str
    content_html: str | None = None
    erules_id: str = ""
    applicability_date: str | None = None
    entry_into_force_date: str | None = None
    regulatory_source: str | None = None


@dataclass
class ParsedEdge:
    source_ref: str           # e.g. "AMC 21.A.91"
    target_ref: str           # e.g. "21.A.91"
    relation: str             # e.g. "ACCEPTABLE_MEANS"
    confidence: float = 1.0
    notes: str | None = None


@dataclass
class ParseResult:
    nodes: list[ParsedNode] = field(default_factory=list)
    edges: list[ParsedEdge] = field(default_factory=list)
    source_document_hash: str = ""
    source_document_title: str = ""
    source_version: str | None = None
    source_pub_time: datetime | None = None
