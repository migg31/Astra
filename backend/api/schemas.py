from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

NodeTypeLiteral = Literal["IR", "AMC", "GM", "CS"]


class NodeSummary(BaseModel):
    node_id: UUID
    node_type: NodeTypeLiteral
    reference_code: str
    title: str | None = None
    hierarchy_path: str


class NodeDetail(NodeSummary):
    content_text: str
    content_html: str | None = None
    content_hash: str
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
