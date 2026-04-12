from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from backend.api.schemas import (
    EdgeOut,
    NeighborsResponse,
    NodeDetail,
    NodeListResponse,
    NodeSummary,
    NodeTypeLiteral,
)
from backend.database.connection import get_session
from backend.database.models import RegulatoryEdge, RegulatoryNode

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


def _to_summary(row: RegulatoryNode) -> NodeSummary:
    return NodeSummary(
        node_id=row.node_id,
        node_type=row.node_type,
        reference_code=row.reference_code,
        title=row.title,
        hierarchy_path=row.hierarchy_path,
        regulatory_source=row.regulatory_source,
    )


def _to_detail(row: RegulatoryNode) -> NodeDetail:
    return NodeDetail(
        node_id=row.node_id,
        node_type=row.node_type,
        reference_code=row.reference_code,
        title=row.title,
        hierarchy_path=row.hierarchy_path,
        content_text=row.content_text,
        content_html=row.content_html,
        content_hash=row.content_hash,
        regulatory_source=row.regulatory_source,
        applicability_date=row.applicability_date,
        entry_into_force_date=row.entry_into_force_date,
        confidence=float(row.confidence),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.get("", response_model=NodeListResponse)
async def list_nodes(
    node_type: NodeTypeLiteral | None = None,
    q: str | None = Query(
        None,
        description="Substring match on reference_code or title (case-insensitive).",
    ),
    hierarchy_prefix: str | None = None,
    limit: int = Query(50, ge=1, le=25000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> NodeListResponse:
    stmt = select(RegulatoryNode).options(load_only(
        RegulatoryNode.node_id,
        RegulatoryNode.node_type,
        RegulatoryNode.reference_code,
        RegulatoryNode.title,
        RegulatoryNode.hierarchy_path,
        RegulatoryNode.regulatory_source,
    ))
    count_stmt = select(func.count()).select_from(RegulatoryNode)

    filters = []
    if node_type:
        filters.append(RegulatoryNode.node_type == node_type)
    if hierarchy_prefix:
        filters.append(RegulatoryNode.hierarchy_path.like(f"{hierarchy_prefix}%"))
    if q:
        like = f"%{q}%"
        filters.append(
            RegulatoryNode.reference_code.ilike(like) | RegulatoryNode.title.ilike(like)
        )

    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    stmt = stmt.order_by(RegulatoryNode.hierarchy_path, RegulatoryNode.reference_code)
    stmt = stmt.limit(limit).offset(offset)

    total = (await session.execute(count_stmt)).scalar_one()
    rows = (await session.execute(stmt)).scalars().all()

    return NodeListResponse(
        total=total,
        limit=limit,
        offset=offset,
        items=[_to_summary(r) for r in rows],
    )


@router.get("/{node_id}", response_model=NodeDetail)
async def get_node(
    node_id: UUID,
    session: AsyncSession = Depends(get_session),
) -> NodeDetail:
    row = await session.get(RegulatoryNode, node_id)
    if row is None:
        raise HTTPException(status_code=404, detail="node not found")
    return _to_detail(row)


@router.get("/{node_id}/neighbors", response_model=NeighborsResponse)
async def get_neighbors(
    node_id: UUID,
    relation: str | None = Query(None, description="Filter edges by relation type."),
    session: AsyncSession = Depends(get_session),
) -> NeighborsResponse:
    node = await session.get(RegulatoryNode, node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="node not found")

    out_stmt = (
        select(RegulatoryEdge, RegulatoryNode)
        .join(RegulatoryNode, RegulatoryNode.node_id == RegulatoryEdge.target_node_id)
        .where(RegulatoryEdge.source_node_id == node_id)
    )
    in_stmt = (
        select(RegulatoryEdge, RegulatoryNode)
        .join(RegulatoryNode, RegulatoryNode.node_id == RegulatoryEdge.source_node_id)
        .where(RegulatoryEdge.target_node_id == node_id)
    )
    if relation:
        out_stmt = out_stmt.where(RegulatoryEdge.relation == relation)
        in_stmt = in_stmt.where(RegulatoryEdge.relation == relation)

    outgoing_rows = (await session.execute(out_stmt)).all()
    incoming_rows = (await session.execute(in_stmt)).all()

    def _edge(edge: RegulatoryEdge, other: RegulatoryNode) -> EdgeOut:
        return EdgeOut(
            edge_id=edge.edge_id,
            relation=edge.relation,
            confidence=float(edge.confidence),
            notes=edge.notes,
            other=_to_summary(other),
        )

    return NeighborsResponse(
        node=_to_summary(node),
        outgoing=[_edge(e, n) for e, n in outgoing_rows],
        incoming=[_edge(e, n) for e, n in incoming_rows],
    )
