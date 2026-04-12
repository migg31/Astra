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
from backend.harvest.catalog import CATALOG
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
    log_lines: List[str] = []
    current_source: Optional[str] = None
    queue: List[str] = []
    completed: List[str] = []

_status = IngestionStatus()
_lock = asyncio.Lock()


def _log(line: str) -> None:
    """Append a timestamped log line to the global status, keep last 200 lines."""
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    _status.log_lines.append(f"[{ts}] {line}")
    if len(_status.log_lines) > 200:
        _status.log_lines = _status.log_lines[-200:]

class SystemStats(BaseModel):
    nodes_count: int
    edges_count: int
    documents_count: int
    embeddings_count: int
    db_size_mb: float
    vector_size_mb: float
    version_snapshots_count: int = 0
    harvest_runs_count: int = 0
    last_harvest_at: str | None = None

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
        
    # Versioning stats
    snapshots = await db.scalar(text("SELECT COUNT(*) FROM regulatory_node_versions"))
    runs = await db.scalar(text("SELECT COUNT(*) FROM document_harvest_runs"))
    last_harvest = await db.scalar(text("SELECT MAX(fetched_at) FROM document_harvest_runs"))

    return SystemStats(
        nodes_count=nodes or 0,
        edges_count=edges or 0,
        documents_count=docs or 0,
        embeddings_count=embeds,
        db_size_mb=round(db_size or 0, 2),
        vector_size_mb=round(vector_size_mb, 2),
        version_snapshots_count=int(snapshots or 0),
        harvest_runs_count=int(runs or 0),
        last_harvest_at=last_harvest.isoformat() if last_harvest else None,
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

async def _run_harvester_task_multi(source_cfgs: list[dict]):
    """Background task: run ingestion sequentially for each source in the list."""
    global _status
    async with _lock:
        _status.is_running = True
        _status.error = None
        _status.log_lines = []
        _status.completed = []
        _status.queue = [c["name"] for c in source_cfgs]
        loop = asyncio.get_running_loop()

        try:
            seen_keys: set[tuple[str, str]] = set()  # shared across all sources to dedup snapshots
            for src_cfg in source_cfgs:
                name = src_cfg["name"]
                _status.current_source = name
                _status.queue = [c["name"] for c in source_cfgs if c["name"] not in _status.completed and c["name"] != name]
                _log(f"=== Starting: {name} ===")

                data_dir = Path("data")

                # Step 1 — Fetch
                _log(f"[{name}] Fetching XML from EASA...")
                try:
                    fetched = await loop.run_in_executor(
                        None,
                        lambda cfg=src_cfg: fetch_easa_xml(data_dir, cfg["url"], cfg["external_id"]),
                    )
                    _log(f"[{name}] Downloaded: {fetched.path.name} ({fetched.path.stat().st_size // 1024} KB)")
                    _log(f"[{name}] Content hash: {fetched.content_hash[:12]}...")
                except Exception as e:
                    _log(f"[{name}] ERROR during fetch: {e}")
                    _status.error = f"{name}: fetch failed — {e}"
                    continue

                # Step 2 — Ingest into Postgres
                _log(f"[{name}] Parsing XML and upserting PostgreSQL...")
                try:
                    report = await loop.run_in_executor(
                        None,
                        lambda f=fetched, cfg=src_cfg: ingest(
                            f.path,
                            source_name=cfg["name"],
                            source_url=f.url,
                            external_id=f.external_id,
                            content_hash=f.content_hash,
                            seen_keys=seen_keys,
                        ),
                    )
                    _log(f"[{name}] Nodes upserted  : {report.get('nodes', 0)}")
                    _log(f"[{name}]   added          : {report.get('nodes_added', 0)}")
                    _log(f"[{name}]   modified       : {report.get('nodes_modified', 0)}")
                    _log(f"[{name}]   unchanged      : {report.get('nodes_unchanged', 0)}")
                    _log(f"[{name}] Edges inserted  : {report.get('edges_inserted', 0)}")
                    pub = report.get('pub_time')
                    if pub:
                        _log(f"[{name}] Publication date: {pub}")
                    _status.last_report = report
                    _status.last_run_at = datetime.now(timezone.utc)
                except Exception as e:
                    _log(f"[{name}] ERROR during ingest: {e}")
                    _status.error = f"{name}: ingest failed — {e}"
                    continue

                _status.completed.append(name)
                _log(f"[{name}] Done.")

            # Step 3 — Re-index vectors (once, after all sources)
            _log("=== Re-indexing vectors (all sources) ===")
            _log("Fetching nodes from PostgreSQL (excluding GROUP + empty)...")
            try:
                await loop.run_in_executor(None, run_embedding_pipeline)
                _log("Vector index rebuilt successfully.")
            except Exception as e:
                _log(f"ERROR during vector re-indexing: {e}")
                _log("Hint: context length exceeded — check MAX_EMBED_CHARS in ingest_embeddings.py")
                _status.error = f"vector re-index failed — {e}"

            _log(f"=== Harvest complete: {len(_status.completed)}/{len(source_cfgs)} sources ===")

        except Exception as e:
            _status.error = str(e)
            _log(f"FATAL ERROR: {e}")
        finally:
            _status.is_running = False
            _status.current_source = None

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


class HarvesterRunRequest(BaseModel):
    sources: List[str] = ["part21"]


@router.post("/harvester/run")
async def start_harvester(
    background_tasks: BackgroundTasks,
    body: HarvesterRunRequest = HarvesterRunRequest(),
    db: AsyncSession = Depends(get_session),
):
    """Trigger ingestion for one or more sources by external_id."""
    if _status.is_running:
        raise HTTPException(status_code=400, detail="Harvester is already running")

    source_cfgs: list[dict] = []
    for source in body.sources:
        row = await db.execute(
            text("SELECT name, base_url, external_id FROM harvest_sources WHERE external_id = :eid"),
            {"eid": source},
        )
        src = row.fetchone()
        if src is None:
            if source not in REGULATORY_SOURCES:
                raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
            source_cfgs.append(REGULATORY_SOURCES[source])
        else:
            source_cfgs.append({"name": src.name, "url": src.base_url, "external_id": src.external_id})

    background_tasks.add_task(_run_harvester_task_multi, source_cfgs)
    names = ", ".join(c["name"] for c in source_cfgs)
    return {"message": f"Harvester started for: {names}"}


@router.get("/catalog")
async def get_catalog(db: AsyncSession = Depends(get_session)):
    """Return the full EASA regulatory catalog with live indexing status from DB."""
    rows = await db.execute(text("""
        SELECT
            hd.title,
            hd.version_label,
            hd.pub_date,
            hd.amended_by,
            COUNT(rn.node_id) AS node_count,
            MIN(SPLIT_PART(rn.hierarchy_path, ' / ', 1)) AS first_root
        FROM harvest_documents hd
        LEFT JOIN regulatory_nodes rn ON rn.source_doc_id = hd.doc_id
        GROUP BY hd.title, hd.version_label, hd.pub_date, hd.amended_by
    """))

    # All indexed documents as list of dicts (preserve original title for frontend matching)
    docs = [
        {
            "title_raw": row["title"] or "",
            "title": (row["title"] or "").lower(),
            "first_root": row["first_root"] or "",
            "version_label": row["version_label"],
            "pub_date": str(row["pub_date"]) if row["pub_date"] else None,
            "amended_by": row["amended_by"],
            "node_count": int(row["node_count"] or 0),
        }
        for row in rows.mappings()
    ]

    def match_doc(pattern: str) -> dict | None:
        """Return first doc whose title matches the SQL ILIKE pattern (%-wildcard)."""
        import re
        # Convert SQL ILIKE pattern (%foo%bar%) to regex
        regex = re.compile(
            ".*".join(re.escape(p) for p in pattern.lower().split("%") if p),
            re.IGNORECASE,
        )
        # Prefer docs with most nodes
        candidates = [d for d in docs if regex.search(d["title"])]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d["node_count"])

    # Pre-fetch per-Part node counts for entries with ref_code_pattern
    part_counts: dict[str, int] = {}
    for entry in CATALOG:
        if entry.doc_title_pattern and entry.ref_code_pattern:
            row = await db.execute(text("""
                SELECT COUNT(rn.node_id)
                FROM regulatory_nodes rn
                JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
                WHERE hd.title ILIKE :title_pat
                  AND rn.node_type != 'GROUP'
                  AND rn.reference_code ~ :ref_pat
            """), {"title_pat": entry.doc_title_pattern, "ref_pat": entry.ref_code_pattern})
            part_counts[entry.id] = int(row.scalar() or 0)

    result = []
    for entry in CATALOG:
        info: dict | None = None
        if entry.doc_title_pattern:
            info = match_doc(entry.doc_title_pattern)
        # Use per-Part count when available, else fall back to full doc count
        node_count = part_counts.get(entry.id, info["node_count"] if info else 0)
        result.append({
            "id": entry.id,
            "name": entry.name,
            "short": entry.short,
            "category": entry.category,
            "domain": entry.domain,
            "description": entry.description,
            "easa_url": entry.easa_url,
            "indexed": info is not None and info["node_count"] > 0,
            "source_title": info["title_raw"] if info else None,
            "source_root": info["first_root"] if info else None,
            "version_label": info["version_label"] if info else None,
            "pub_date": info["pub_date"] if info else None,
            "amended_by": info["amended_by"] if info else None,
            "node_count": node_count,
        })
    return result
