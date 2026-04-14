from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

NodeTypeLiteral = Literal["IR", "AMC", "GM", "CS", "GROUP"]


class NodeSummary(BaseModel):
    node_id: UUID
    node_type: NodeTypeLiteral
    reference_code: str
    title: str | None = None
    hierarchy_path: str
    regulatory_source: str | None = None


class NodeDetail(NodeSummary):
    content_text: str
    content_html: str | None = None
    content_hash: str
    regulatory_source: str | None = None
    applicability_date: str | None = None
    entry_into_force_date: str | None = None
    confidence: float
    created_at: datetime
    updated_at: datetime


class NodeListResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: list[NodeSummary]


class EdgeOut(BaseModel):
    edge_id: UUID
    relation: str
    confidence: float
    notes: str | None = None
    other: NodeSummary = Field(
        ...,
        description="The node at the other end of the edge (not the one being queried).",
    )


class NeighborsResponse(BaseModel):
    node: NodeSummary
    outgoing: list[EdgeOut] = Field(
        default_factory=list,
        description="Edges where the queried node is the source.",
    )
    incoming: list[EdgeOut] = Field(
        default_factory=list,
        description="Edges where the queried node is the target.",
    )


# --- Graph endpoint schemas ---

class GraphNode(BaseModel):
    node_id: str
    node_type: NodeTypeLiteral
    reference_code: str
    title: str | None = None
    hierarchy_path: str


class GraphEdge(BaseModel):
    edge_id: str
    source_node_id: str
    target_node_id: str
    relation: str
    confidence: float


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# --- Regulatory Sources ---

class SourceUrls(BaseModel):
    xml: str | None = None
    html: str | None = None
    pdf: str | None = None


class RegulatorySourceOut(BaseModel):
    source_id: UUID
    name: str
    base_url: str
    urls: SourceUrls | None = None
    external_id: str | None
    format: str
    frequency: str
    enabled: bool
    last_sync_at: datetime | None


class RegulatorySourceCreate(BaseModel):
    name: str
    base_url: str
    urls: SourceUrls | None = None
    external_id: str
    format: str = "MIXED"
    frequency: str = "monthly"
    enabled: bool = True


class RegulatorySourceUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    urls: SourceUrls | None = None
    enabled: bool | None = None
