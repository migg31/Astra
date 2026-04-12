"""GET /api/graph — Full regulatory knowledge graph (nodes + edges).

Returns all nodes and all edges in a single call, intended for the
MAP view's D3 force simulation. No pagination — the corpus is small
(~103 nodes, ~139 edges) and the client needs the full graph to render.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import GraphEdge, GraphNode, GraphResponse
from backend.database.connection import get_session
from backend.database.models import RegulatoryEdge, RegulatoryNode

router = APIRouter(prefix="/api/graph", tags=["graph"])


@router.get("", response_model=GraphResponse)
async def get_graph(session: AsyncSession = Depends(get_session)) -> GraphResponse:
    nodes_rows = (await session.execute(select(RegulatoryNode))).scalars().all()
    edges_rows = (await session.execute(select(RegulatoryEdge))).scalars().all()

    nodes = [
        GraphNode(
            node_id=str(r.node_id),
            node_type=r.node_type,
            reference_code=r.reference_code,
            title=r.title,
            hierarchy_path=r.hierarchy_path,
        )
        for r in nodes_rows
    ]

    edges = [
        GraphEdge(
            edge_id=str(e.edge_id),
            source_node_id=str(e.source_node_id),
            target_node_id=str(e.target_node_id),
            relation=e.relation,
            confidence=float(e.confidence),
        )
        for e in edges_rows
    ]

    return GraphResponse(nodes=nodes, edges=edges)
