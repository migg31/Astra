"""Version history endpoints for regulatory nodes and documents."""
from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_session
from backend.harvest.easa_fetcher import check_latest_version

router = APIRouter(prefix="/api/history", tags=["history"])


# ── Schemas ──────────────────────────────────────────────────────────────────

class NodeVersionOut(BaseModel):
    version_id: str
    version_label: str
    change_type: str
    content_hash: str
    fetched_at: str
    diff_prev: list[dict] | None = None

    class Config:
        from_attributes = True


class NodeHistoryResponse(BaseModel):
    node_id: str
    versions: list[NodeVersionOut]


class HarvestRunOut(BaseModel):
    run_id: str
    version_label: str
    fetched_at: str
    nodes_added: int
    nodes_modified: int
    nodes_deleted: int
    nodes_unchanged: int
    nodes_total: int


class DocumentHistoryResponse(BaseModel):
    source_title: str
    runs: list[HarvestRunOut]


class VersionCheckOut(BaseModel):
    source_root: str
    source_title: str
    easa_url: str
    indexed_version: str | None
    latest_version: str | None
    is_outdated: bool
    checked_at: str


# ── Node history ──────────────────────────────────────────────────────────────

@router.get("/nodes/{node_id}", response_model=NodeHistoryResponse)
async def get_node_history(
    node_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return all version snapshots for a node, newest first."""
    rows = await session.execute(
        text("""
            SELECT version_id::text, version_label, change_type,
                   content_hash, fetched_at, diff_prev
            FROM regulatory_node_versions
            WHERE node_id = :nid
            ORDER BY fetched_at DESC
        """),
        {"nid": str(node_id)},
    )
    versions = []
    for r in rows.mappings():
        versions.append(NodeVersionOut(
            version_id=r["version_id"],
            version_label=r["version_label"],
            change_type=r["change_type"],
            content_hash=r["content_hash"],
            fetched_at=r["fetched_at"].isoformat(),
            diff_prev=r["diff_prev"],
        ))

    if not versions:
        # Node exists but has no recorded history yet (pre-versioning data)
        node = await session.execute(
            text("SELECT node_id FROM regulatory_nodes WHERE node_id = :nid"),
            {"nid": str(node_id)},
        )
        if not node.first():
            raise HTTPException(status_code=404, detail="Node not found")

    return NodeHistoryResponse(node_id=str(node_id), versions=versions)


@router.get("/nodes/{node_id}/diff/{version_id}", response_model=NodeVersionOut)
async def get_node_version_diff(
    node_id: UUID,
    version_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Return a specific version snapshot including the word-level diff."""
    row = await session.execute(
        text("""
            SELECT version_id::text, version_label, change_type,
                   content_hash, fetched_at, diff_prev
            FROM regulatory_node_versions
            WHERE node_id = :nid AND version_id = :vid
        """),
        {"nid": str(node_id), "vid": str(version_id)},
    )
    r = row.mappings().first()
    if not r:
        raise HTTPException(status_code=404, detail="Version not found")

    return NodeVersionOut(
        version_id=r["version_id"],
        version_label=r["version_label"],
        change_type=r["change_type"],
        content_hash=r["content_hash"],
        fetched_at=r["fetched_at"].isoformat(),
        diff_prev=r["diff_prev"],
    )


# ── Document harvest run history ──────────────────────────────────────────────

@router.get("/documents/{source_root}", response_model=DocumentHistoryResponse)
async def get_document_history(
    source_root: str,
    session: AsyncSession = Depends(get_session),
):
    """Return harvest run history for a document identified by its source_root."""
    rows = await session.execute(
        text("""
            SELECT dhr.run_id::text, dhr.version_label, dhr.fetched_at,
                   dhr.nodes_added, dhr.nodes_modified, dhr.nodes_deleted,
                   dhr.nodes_unchanged, dhr.nodes_total,
                   hd.title
            FROM document_harvest_runs dhr
            JOIN harvest_documents hd ON hd.doc_id = dhr.doc_id
            WHERE hd.title ILIKE :source
               OR hd.amended_by ILIKE :source
               OR EXISTS (
                   SELECT 1 FROM regulatory_nodes rn
                   WHERE rn.source_doc_id = hd.doc_id
                     AND SPLIT_PART(rn.hierarchy_path, ' / ', 1) = :exact
                   LIMIT 1
               )
            ORDER BY dhr.fetched_at DESC
        """),
        {"source": f"%{source_root}%", "exact": source_root},
    )
    runs = []
    source_title = source_root
    for r in rows.mappings():
        source_title = r["title"]
        runs.append(HarvestRunOut(
            run_id=r["run_id"],
            version_label=r["version_label"],
            fetched_at=r["fetched_at"].isoformat(),
            nodes_added=r["nodes_added"],
            nodes_modified=r["nodes_modified"],
            nodes_deleted=r["nodes_deleted"],
            nodes_unchanged=r["nodes_unchanged"],
            nodes_total=r["nodes_total"],
        ))

    return DocumentHistoryResponse(source_title=source_title, runs=runs)


# ── Version staleness check ───────────────────────────────────────────────────

@router.get("/version-check", response_model=list[VersionCheckOut])
async def version_check(session: AsyncSession = Depends(get_session)):
    """Check all indexed documents against EASA website for version staleness.

    Makes one lightweight HTTP request per indexed document (reads only 32 KB
    of HTML — no ZIP download). Results are returned sorted: outdated first.
    """
    # Fetch all indexed documents with their EASA URL and indexed version
    rows = await session.execute(text("""
        SELECT
            hd.title,
            hd.version_label,
            hd.url                          AS easa_url,
            MIN(SPLIT_PART(rn.hierarchy_path, ' / ', 1)) AS source_root
        FROM harvest_documents hd
        LEFT JOIN regulatory_nodes rn ON rn.source_doc_id = hd.doc_id
        GROUP BY hd.title, hd.version_label, hd.url
        HAVING COUNT(rn.node_id) > 0
        ORDER BY hd.title
    """))
    docs = list(rows.mappings())

    if not docs:
        return []

    # Run checks concurrently (one per doc) in a thread pool to avoid blocking
    def _check(doc: dict) -> VersionCheckOut:
        result = check_latest_version(doc["easa_url"], doc["version_label"])
        return VersionCheckOut(
            source_root=doc["source_root"] or doc["title"],
            source_title=doc["title"],
            easa_url=doc["easa_url"],
            indexed_version=result.indexed_version,
            latest_version=result.latest_version,
            is_outdated=result.is_outdated,
            checked_at=result.checked_at.isoformat(),
        )

    loop = asyncio.get_event_loop()
    tasks = [
        loop.run_in_executor(None, _check, dict(doc))
        for doc in docs
    ]
    results: list[VersionCheckOut] = await asyncio.gather(*tasks)

    # Sort: outdated first, then alphabetical
    return sorted(results, key=lambda r: (not r.is_outdated, r.source_title))
