from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.schemas import RegulatorySourceCreate, RegulatorySourceOut, RegulatorySourceUpdate
from backend.database.connection import get_session
from backend.rag.store import count as count_embeddings, _CHROMA_PATH
from backend.harvest.ingest import (
    ingest,
    fetch_easa_xml,
    REGULATORY_SOURCES,
)
from backend.rag.ingest_embeddings import main as run_embedding_pipeline
from backend.rag.embedder import _get_client as get_ollama_client, EMBED_MODEL
from backend.rag.responder import CHAT_MODEL

router = APIRouter(prefix="/api/admin", tags=["admin"])

# Global state for ingestion tracking
class IngestionStatus(BaseModel):
    is_running: bool = False
    last_run_at: Optional[datetime] = None
    last_report: Optional[Dict] = None
    error: Optional[str] = None

_status = IngestionStatus()
_lock = asyncio.Lock()

class SystemStats(BaseModel):
    nodes_count: int
    edges_count: int
    documents_count: int
    embeddings_count: int
    db_size_mb: float
    vector_size_mb: float

class HealthStatus(BaseModel):
    postgres: bool
    chroma: bool
    ollama_server: bool
    ollama_model_embed: bool
    ollama_model_chat: bool

class SystemConfig(BaseModel):
    harvester_source_url: str
    harvester_name: str
    harvester_frequency: str
    harvester_format: str
    data_directory: str
    db_host: str
    ollama_base_url: str

@router.get("/stats", response_model=SystemStats)
async def get_stats(db: AsyncSession = Depends(get_session)):
    """Fetch global statistics from PostgreSQL and ChromaDB."""
    # Postgres stats
    nodes = await db.scalar(text("SELECT COUNT(*) FROM regulatory_nodes"))
    edges = await db.scalar(text("SELECT COUNT(*) FROM regulatory_edges"))
    docs = await db.scalar(text("SELECT COUNT(*) FROM harvest_documents"))
    
    # DB Size (approximate)
    db_size = await db.scalar(text("SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"))
    
    # Chroma stats
    embeds = 0
    vector_size_mb = 0.0
    try:
        embeds = count_embeddings()
        if _CHROMA_PATH.exists():
            total_size = sum(f.stat().st_size for f in _CHROMA_PATH.rglob('*') if f.is_file())
            vector_size_mb = total_size / (1024 * 1024)
    except Exception:
        pass
        
    return SystemStats(
        nodes_count=nodes or 0,
        edges_count=edges or 0,
        documents_count=docs or 0,
        embeddings_count=embeds,
        db_size_mb=round(db_size or 0, 2),
        vector_size_mb=round(vector_size_mb, 2)
    )

@router.get("/health", response_model=HealthStatus)
async def check_health(db: AsyncSession = Depends(get_session)):
    """Check connectivity to all backend services."""
    postgres_ok = False
    try:
        await db.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    chroma_ok = False
    try:
        count_embeddings()
        chroma_ok = True
    except Exception:
        pass

    ollama_server_ok = False
    ollama_model_embed_ok = False
    ollama_model_chat_ok = False
    try:
        client = get_ollama_client()
        # Test basic connectivity to Ollama
        models = client.models.list()
        ollama_server_ok = True
        
        # Check specific models
        model_ids = [m.id for m in models.data]
        ollama_model_embed_ok = any(m == EMBED_MODEL or m.startswith(EMBED_MODEL + ":") for m in model_ids)
        ollama_model_chat_ok = any(m == CHAT_MODEL or m.startswith(CHAT_MODEL + ":") for m in model_ids)
    except Exception:
        pass

    return HealthStatus(
        postgres=postgres_ok,
        chroma=chroma_ok,
        ollama_server=ollama_server_ok,
        ollama_model_embed=ollama_model_embed_ok,
        ollama_model_chat=ollama_model_chat_ok
    )

@router.get("/config", response_model=SystemConfig)
async def get_config():
    """Expose system and harvester configuration."""
    from backend.rag.embedder import OLLAMA_BASE_URL
    from urllib.parse import urlparse
    from backend.config import settings
    
    db_url = urlparse(settings.database_url)
    # Use part21 as the default reference for config display
    default_source = REGULATORY_SOURCES["part21"]
    
    return SystemConfig(
        harvester_source_url=default_source["url"],
        harvester_name=default_source["name"],
        harvester_frequency="monthly",
        harvester_format="MIXED",
        data_directory=str(Path("data").resolve()),
        db_host=db_url.hostname or "localhost",
        ollama_base_url=OLLAMA_BASE_URL
    )

@router.get("/harvester/status", response_model=IngestionStatus)
async def get_harvester_status():
    """Get the current state of the ingestion process."""
    return _status

async def _run_harvester_task_cfg(source_cfg: dict):
    """Background task: fetch → parse → persist → embed for a given source config dict."""
    global _status
    async with _lock:
        _status.is_running = True
        _status.error = None
        try:
            data_dir = Path("data")

            # 1. Fetch
            fetched = fetch_easa_xml(data_dir, source_cfg["url"], source_cfg["external_id"])

            # 2. Ingest into Postgres
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None,
                lambda: ingest(
                    fetched.path,
                    source_name=source_cfg["name"],
                    source_url=fetched.url,
                    external_id=fetched.external_id,
                    content_hash=fetched.content_hash,
                ),
            )

            # 3. Re-index vectors
            await loop.run_in_executor(None, run_embedding_pipeline)

            _status.last_report = report
            _status.last_run_at = datetime.now(timezone.utc)
        except Exception as e:
            _status.error = str(e)
        finally:
            _status.is_running = False

# ── Regulatory Sources CRUD ──────────────────────────────────────────────────

@router.get("/sources", response_model=list[RegulatorySourceOut])
async def list_sources(db: AsyncSession = Depends(get_session)):
    """List all regulatory sources from the database."""
    rows = await db.execute(
        text("""
            SELECT source_id, name, base_url, external_id, format, frequency, enabled, last_sync_at
            FROM harvest_sources
            ORDER BY name
        """)
    )
    return [RegulatorySourceOut(**dict(r._mapping)) for r in rows]


@router.post("/sources", response_model=RegulatorySourceOut, status_code=201)
async def create_source(body: RegulatorySourceCreate, db: AsyncSession = Depends(get_session)):
    """Add a new regulatory source."""
    row = await db.execute(
        text("""
            INSERT INTO harvest_sources (name, base_url, external_id, format, frequency, enabled)
            VALUES (:name, :base_url, :external_id, :format, :frequency, :enabled)
            RETURNING source_id, name, base_url, external_id, format, frequency, enabled, last_sync_at
        """),
        body.model_dump(),
    )
    await db.commit()
    return RegulatorySourceOut(**dict(row.fetchone()._mapping))


@router.patch("/sources/{source_id}", response_model=RegulatorySourceOut)
async def update_source(
    source_id: str,
    body: RegulatorySourceUpdate,
    db: AsyncSession = Depends(get_session),
):
    """Update name, URL, or enabled flag of a source."""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["source_id"] = source_id
    row = await db.execute(
        text(f"""
            UPDATE harvest_sources
            SET {set_clause}
            WHERE source_id = :source_id
            RETURNING source_id, name, base_url, external_id, format, frequency, enabled, last_sync_at
        """),
        updates,
    )
    await db.commit()
    result = row.fetchone()
    if result is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return RegulatorySourceOut(**dict(result._mapping))


@router.delete("/sources/{source_id}", status_code=204)
async def delete_source(source_id: str, db: AsyncSession = Depends(get_session)):
    """Delete a source (only if it has no associated documents)."""
    docs = await db.scalar(
        text("SELECT COUNT(*) FROM harvest_documents WHERE source_id = :sid"),
        {"sid": source_id},
    )
    if docs and docs > 0:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete: {docs} document(s) ingested from this source",
        )
    await db.execute(
        text("DELETE FROM harvest_sources WHERE source_id = :sid"), {"sid": source_id}
    )
    await db.commit()


# ── Harvester trigger ─────────────────────────────────────────────────────────

@router.get("/harvester/sources")
async def get_harvester_sources(db: AsyncSession = Depends(get_session)):
    """List enabled regulatory sources for the harvester dropdown."""
    rows = await db.execute(
        text("""
            SELECT source_id::text AS id, name, external_id, enabled
            FROM harvest_sources
            ORDER BY name
        """)
    )
    return [dict(r._mapping) for r in rows]


@router.post("/harvester/run")
async def start_harvester(
    background_tasks: BackgroundTasks,
    source: str = "part21",
    db: AsyncSession = Depends(get_session),
):
    """Trigger ingestion for a source identified by external_id."""
    if _status.is_running:
        raise HTTPException(status_code=400, detail="Harvester is already running")

    row = await db.execute(
        text("""
            SELECT name, base_url, external_id
            FROM harvest_sources
            WHERE external_id = :eid
        """),
        {"eid": source},
    )
    src = row.fetchone()
    if src is None:
        # Fallback to hardcoded dict for backward compatibility
        if source not in REGULATORY_SOURCES:
            raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
        src_cfg = REGULATORY_SOURCES[source]
    else:
        src_cfg = {"name": src.name, "url": src.base_url, "external_id": src.external_id}

    background_tasks.add_task(_run_harvester_task_cfg, src_cfg)
    return {"message": f"Harvester started for {src_cfg['name']}"}
