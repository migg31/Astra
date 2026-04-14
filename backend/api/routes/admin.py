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
from backend.rag.store import count as count_embeddings, purge as purge_store
from backend.harvest.ingest import (
    ingest,
    _load_sources_from_db,
)
from backend.harvest.easa_fetcher import fetch_easa_document
from backend.rag.ingest_embeddings import main as run_embedding_pipeline
from backend.rag.embedder import _get_client as get_ollama_client, EMBED_MODEL
from backend.config import settings

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
    embed_done: int = 0
    embed_total: int = 0

_status = IngestionStatus()
_lock = asyncio.Lock()


def _log(line: str) -> None:
    """Append a timestamped log line to the global status, keep last 200 lines."""
    # Parse embedding progress lines: "[embed:progress] done/total pct"
    if line.startswith("[embed:progress]"):
        parts = line.split()
        if len(parts) >= 2:
            try:
                done, total = parts[1].split("/")
                _status.embed_done = int(done)
                _status.embed_total = int(total)
            except Exception:
                pass
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
    pgvector: bool
    ollama_server: bool
    ollama_model_embed: bool
    ollama_model_chat: bool
    ollama_server_error: str | None = None
    ollama_model_embed_error: str | None = None
    ollama_model_chat_error: str | None = None

class SystemConfig(BaseModel):
    harvester_source_url: str
    harvester_name: str
    harvester_frequency: str
    harvester_format: str
    data_directory: str
    db_host: str
    ollama_base_url: str
    chat_model: str
    embed_model: str
    chat_provider: str  # "local" | "groq" | "openai" | "other"

@router.get("/stats", response_model=SystemStats)
async def get_stats(db: AsyncSession = Depends(get_session)):
    """Fetch global statistics from PostgreSQL and ChromaDB."""
    # Postgres stats
    nodes = await db.scalar(text("SELECT COUNT(*) FROM regulatory_nodes"))
    edges = await db.scalar(text("SELECT COUNT(*) FROM regulatory_edges"))
    docs = await db.scalar(text("SELECT COUNT(*) FROM harvest_documents"))
    
    # DB Size (approximate)
    db_size = await db.scalar(text("SELECT pg_database_size(current_database()) / 1024.0 / 1024.0"))
    
    # pgvector stats
    embeds = 0
    vector_size_mb = 0.0
    try:
        embeds = count_embeddings()
        vector_size_mb = float(await db.scalar(text(
            "SELECT pg_total_relation_size('node_embeddings') / 1024.0 / 1024.0"
        )) or 0)
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

    pgvector_ok = False
    try:
        count_embeddings()
        pgvector_ok = True
    except Exception:
        pass

    # ── Embed check (always Ollama local) ────────────────────────────────────
    ollama_server_ok = False
    ollama_model_embed_ok = False
    ollama_server_error: str | None = None
    ollama_model_embed_error: str | None = None
    try:
        embed_client = get_ollama_client()
        models = embed_client.models.list()
        ollama_server_ok = True
        model_ids = [m.id for m in models.data]
        if any(m == EMBED_MODEL or m.startswith(EMBED_MODEL + ":") for m in model_ids):
            ollama_model_embed_ok = True
        else:
            ollama_model_embed_error = f"Model '{EMBED_MODEL}' not found. Available: {', '.join(model_ids[:5]) or 'none'}"
    except Exception as e:
        ollama_server_error = str(e)
        ollama_model_embed_error = str(e)

    # ── Chat check (may be cloud provider) ───────────────────────────────────
    ollama_model_chat_ok = False
    ollama_model_chat_error: str | None = None
    chat_base = settings.ollama_base_url.lower()
    is_local_chat = "localhost" in chat_base or "127.0.0.1" in chat_base
    try:
        from openai import OpenAI as _OAI
        chat_client = _OAI(base_url=settings.ollama_base_url, api_key=settings.ollama_api_key)
        if is_local_chat:
            chat_model_ids = [m.id for m in chat_client.models.list().data]
            if any(m == settings.ollama_model or m.startswith(settings.ollama_model + ":") for m in chat_model_ids):
                ollama_model_chat_ok = True
            else:
                ollama_model_chat_error = f"Model '{settings.ollama_model}' not found. Available: {', '.join(chat_model_ids[:5]) or 'none'}"
        else:
            chat_client.chat.completions.create(
                model=settings.ollama_model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
            )
            ollama_model_chat_ok = True
    except Exception as e:
        ollama_model_chat_error = str(e)

    return HealthStatus(
        postgres=postgres_ok,
        pgvector=pgvector_ok,
        ollama_server=ollama_server_ok,
        ollama_model_embed=ollama_model_embed_ok,
        ollama_model_chat=ollama_model_chat_ok,
        ollama_server_error=ollama_server_error,
        ollama_model_embed_error=ollama_model_embed_error,
        ollama_model_chat_error=ollama_model_chat_error,
    )

@router.get("/config", response_model=SystemConfig)
async def get_config():
    """Expose system and harvester configuration."""
    from backend.rag.embedder import OLLAMA_BASE_URL
    from urllib.parse import urlparse
    from backend.config import settings
    
    db_url = urlparse(settings.database_url)
    first_source = next(iter(_load_sources_from_db().values()), {})
    default_url = first_source.get("urls", {}).get("xml") or first_source.get("url", "")
    
    base = settings.ollama_base_url.lower()
    if "groq.com" in base:
        provider = "groq"
    elif "openai.com" in base:
        provider = "openai"
    elif "localhost" in base or "127.0.0.1" in base:
        provider = "local"
    else:
        provider = "other"

    return SystemConfig(
        harvester_source_url=default_url,
        harvester_name=first_source.get("name", ""),
        harvester_frequency="monthly",
        harvester_format="MIXED",
        data_directory=str(Path("data").resolve()),
        db_host=db_url.hostname or "localhost",
        ollama_base_url=OLLAMA_BASE_URL,
        chat_model=settings.ollama_model,
        embed_model=settings.embed_model,
        chat_provider=provider,
    )

@router.get("/harvester/status", response_model=IngestionStatus)
async def get_harvester_status():
    """Get the current state of the ingestion process."""
    return _status

async def _run_harvester_task_multi(source_cfgs: list[dict], reindex_vectors: bool = False):
    """Background task: run ingestion sequentially for each source in the list."""
    global _status
    async with _lock:
        _status.is_running = True
        _status.error = None
        _status.log_lines = []
        _status.completed = []
        _status.embed_done = 0
        _status.embed_total = 0
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
                _log(f"[{name}] Fetching document from EASA...")
                try:
                    # Support both single 'url' (from DB) and 'urls' dict (from REGULATORY_SOURCES)
                    urls = src_cfg.get("urls") or {"xml": src_cfg.get("url")}
                    fetched = await loop.run_in_executor(
                        None,
                        lambda u=urls: fetch_easa_document(data_dir, u, src_cfg["external_id"]),
                    )
                    _log(f"[{name}] Downloaded: {fetched.path.name} ({fetched.path.stat().st_size // 1024} KB, format: {fetched.format})")
                    _log(f"[{name}] Content hash: {fetched.content_hash[:12]}...")
                except Exception as e:
                    _log(f"[{name}] ERROR during fetch: {e}")
                    _status.error = f"{name}: fetch failed — {e}"
                    continue

                # Step 2 — Ingest into Postgres
                _log(f"[{name}] Parsing {fetched.format.upper()} and upserting PostgreSQL...")
                try:
                    report = await loop.run_in_executor(
                        None,
                        lambda f=fetched, cfg=src_cfg: ingest(
                            f.path,
                            source_name=cfg["name"],
                            source_url=f.url,
                            external_id=f.external_id,
                            content_hash=f.content_hash,
                            doc_format=f.format,
                            use_smart_parser=cfg.get("use_smart_parser", True),
                            seen_keys=seen_keys,
                            is_latest=True,
                            progress_callback=_log
                        ),
                    )
                    _log(f"[{name}] Nodes upserted  : {report.get('nodes', 0)}")
                    _log(f"[{name}]   added          : {report.get('nodes_added', 0)}")
                    _log(f"[{name}]   modified       : {report.get('nodes_modified', 0)}")
                    _log(f"[{name}]   deleted        : {report.get('nodes_deleted', 0)}")
                    _log(f"[{name}]   unchanged      : {report.get('nodes_unchanged', 0)}")
                    edges_new = report.get('edges_inserted', 0)
                    edges_skip = report.get('edges_skipped', 0)
                    _log(f"[{name}] Edges           : {edges_new} new, {edges_skip} already existed")
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

            # Step 3 — Re-index vectors (optional)
            if reindex_vectors:
                _log("=== Re-indexing vectors (all sources) ===")
                _log("Fetching nodes from PostgreSQL (excluding GROUP + empty)...")
                try:
                    await loop.run_in_executor(None, lambda: run_embedding_pipeline(on_progress=_log))
                    _log("Vector index rebuilt successfully.")
                except Exception as e:
                    _log(f"ERROR during vector re-indexing: {e}")
                    _log("Hint: context length exceeded — check MAX_EMBED_CHARS in ingest_embeddings.py")
                    _status.error = f"vector re-index failed — {e}"
            else:
                _log("=== Vector re-indexing skipped (pass reindex_vectors=true to enable) ===")

            _log(f"=== Harvest complete: {len(_status.completed)}/{len(source_cfgs)} sources ===")

        except Exception as e:
            _status.error = str(e)
            _log(f"FATAL ERROR: {e}")
        finally:
            _status.is_running = False
            _status.current_source = None

async def _run_embeddings_task():
    """Background task: run embedding pipeline only (no harvest)."""
    global _status
    async with _lock:
        _status.is_running = True
        _status.error = None
        _status.log_lines = []
        _status.embed_done = 0
        _status.embed_total = 0
        loop = asyncio.get_running_loop()
        try:
            _log("=== Re-indexing vectors ===")
            await loop.run_in_executor(None, lambda: run_embedding_pipeline(on_progress=_log))
            _log("=== Vector re-index complete ===")
        except Exception as e:
            _status.error = str(e)
            _log(f"ERROR: {e}")
        finally:
            _status.is_running = False
            _status.current_source = None
            _status.last_run_at = datetime.now(timezone.utc)


@router.post("/purge", status_code=200)
async def purge_database():
    """Truncate all indexed data (nodes, documents, snapshots, embeddings).
    Preserves doc_sources, doc_categories, doc_domains, harvest_sources."""
    if _status.is_running:
        raise HTTPException(status_code=409, detail="A harvest/embed task is running. Wait for it to finish before purging.")
    deleted = purge_store()
    return {
        "ok": True,
        "deleted": deleted,
        "message": f"Purged: {deleted.get('regulatory_nodes', 0)} nodes, "
                   f"{deleted.get('harvest_documents', 0)} documents, "
                   f"{deleted.get('node_embeddings', 0)} embeddings.",
    }


@router.post("/embeddings/run", status_code=202)
async def run_embeddings(background_tasks: BackgroundTasks):
    """Trigger embedding re-indexing pipeline (no harvest)."""
    if _status.is_running:
        raise HTTPException(status_code=409, detail="A task is already running.")
    background_tasks.add_task(_run_embeddings_task)
    return {"message": "Embedding pipeline started."}


# ── Regulatory Sources CRUD ──────────────────────────────────────────────────

@router.get("/sources", response_model=list[RegulatorySourceOut])
async def list_sources(db: AsyncSession = Depends(get_session)):
    """List all regulatory sources from the database."""
    rows = await db.execute(
        text("""
            SELECT source_id, name, base_url, urls, external_id, format, frequency, enabled, last_sync_at
            FROM harvest_sources
            ORDER BY name
        """)
    )
    return [RegulatorySourceOut(**dict(r._mapping)) for r in rows]


@router.post("/sources", response_model=RegulatorySourceOut, status_code=201)
async def create_source(body: RegulatorySourceCreate, db: AsyncSession = Depends(get_session)):
    """Add a new regulatory source."""
    # Ensure urls is converted to dict for JSONB column
    data = body.model_dump()
    if data.get("urls"):
        import json
        data["urls"] = json.dumps(data["urls"])

    row = await db.execute(
        text("""
            INSERT INTO harvest_sources (name, base_url, urls, external_id, format, frequency, enabled)
            VALUES (:name, :base_url, :urls, :external_id, :format, :frequency, :enabled)
            RETURNING source_id, name, base_url, urls, external_id, format, frequency, enabled, last_sync_at
        """),
        data,
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
    updates = {k: v for k, v in body.model_dump().items() if v is not None or k == "enabled"}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "urls" in updates and updates["urls"]:
        import json
        updates["urls"] = json.dumps(updates["urls"])

    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["source_id"] = source_id
    row = await db.execute(
        text(f"""
            UPDATE harvest_sources
            SET {set_clause}
            WHERE source_id = :source_id
            RETURNING source_id, name, base_url, urls, external_id, format, frequency, enabled, last_sync_at
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
    sources: List[str] = []
    reindex_vectors: bool = False


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
            text("SELECT name, base_url, external_id, enabled FROM harvest_sources WHERE external_id = :eid"),
            {"eid": source},
        )
        src = row.fetchone()
        if src is None:
            raise HTTPException(status_code=404, detail=f"Source '{source}' not found")
        if not src.enabled:
            _log(f"[{src.name}] Skipped (disabled)")
            continue
        db_sources = _load_sources_from_db()
        db_cfg = db_sources.get(src.external_id, {})
        cfg = {
            "name": src.name,
            "url": src.base_url,
            "external_id": src.external_id,
            "urls": db_cfg.get("urls", {"xml": src.base_url}),
            "use_smart_parser": db_cfg.get("use_smart_parser", True),
        }
        source_cfgs.append(cfg)

    background_tasks.add_task(_run_harvester_task_multi, source_cfgs, body.reindex_vectors)
    names = ", ".join(c["name"] for c in source_cfgs)
    return {"message": f"Harvester started for: {names}"}


@router.get("/catalog/meta")
async def get_catalog_meta(db: AsyncSession = Depends(get_session)):
    """Return available categories and domains for the catalog admin UI."""
    cats = await db.execute(text("SELECT id, label FROM doc_categories ORDER BY sort_order"))
    doms = await db.execute(text("SELECT id, label FROM doc_domains ORDER BY sort_order"))
    return {
        "categories": [{"id": r[0], "label": r[1]} for r in cats],
        "domains":    [{"id": r[0], "label": r[1]} for r in doms],
    }


@router.get("/catalog")
async def get_catalog(db: AsyncSession = Depends(get_session)):
    """Return the full EASA regulatory catalog with live indexing status from DB."""
    # ── Fetch all indexed harvest documents ──────────────────────────────────
    rows = await db.execute(text("""
        SELECT
            hd.title,
            hd.version_label,
            hd.pub_date,
            hd.amended_by,
            COUNT(rn.node_id) AS node_count,
            (
                SELECT SPLIT_PART(rn2.hierarchy_path, ' / ', 1)
                FROM regulatory_nodes rn2
                WHERE rn2.source_doc_id = hd.doc_id
                  AND rn2.hierarchy_path IS NOT NULL
                  AND rn2.hierarchy_path != ''
                GROUP BY SPLIT_PART(rn2.hierarchy_path, ' / ', 1)
                ORDER BY COUNT(*) DESC
                LIMIT 1
            ) AS first_root
        FROM harvest_documents hd
        LEFT JOIN regulatory_nodes rn ON rn.source_doc_id = hd.doc_id
        GROUP BY hd.doc_id, hd.title, hd.version_label, hd.pub_date, hd.amended_by
    """))
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
        import re
        regex = re.compile(
            ".*".join(re.escape(p) for p in pattern.lower().split("%") if p),
            re.IGNORECASE,
        )
        candidates = [d for d in docs if regex.search(d["title"])]
        if not candidates:
            return None
        return max(candidates, key=lambda d: d["node_count"])

    # ── Fetch catalog entries from DB ─────────────────────────────────────────
    src_rows = await db.execute(text("""
        SELECT ds.id, ds.name, ds.short, ds.category_id, ds.domain_id,
               ds.description, ds.easa_url, ds.harvest_key,
               ds.doc_title_pattern, ds.ref_code_pattern,
               ds.is_active, ds.sort_order
        FROM doc_sources ds
        ORDER BY ds.sort_order, ds.id
    """))
    entries = list(src_rows.mappings())

    # ── Per-Part node counts for entries with ref_code_pattern ───────────────
    part_counts: dict[str, int] = {}
    for entry in entries:
        if entry["doc_title_pattern"] and entry["ref_code_pattern"]:
            row = await db.execute(text("""
                SELECT COUNT(rn.node_id)
                FROM regulatory_nodes rn
                JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
                WHERE hd.title ILIKE :title_pat
                  AND rn.node_type != 'GROUP'
                  AND rn.reference_code ~ :ref_pat
            """), {"title_pat": entry["doc_title_pattern"], "ref_pat": entry["ref_code_pattern"]})
            part_counts[entry["id"]] = int(row.scalar() or 0)

    # ── Fetch harvest_sources enabled status + source_id ─────────────────────
    hs_rows = await db.execute(text("SELECT external_id, enabled, source_id::text FROM harvest_sources"))
    harvest_sources_map: dict[str, dict] = {r[0]: {"enabled": r[1], "source_id": r[2]} for r in hs_rows}
    harvest_enabled: dict[str, bool] = {k: v["enabled"] for k, v in harvest_sources_map.items()}

    result = []
    for entry in entries:
        info: dict | None = None
        if entry["doc_title_pattern"]:
            info = match_doc(entry["doc_title_pattern"])
        node_count = part_counts.get(entry["id"], info["node_count"] if info else 0)
        result.append({
            "id":             entry["id"],
            "name":           entry["name"],
            "short":          entry["short"],
            "category":       entry["category_id"],
            "domain":         entry["domain_id"],
            "description":    entry["description"],
            "easa_url":       entry["easa_url"],
            "is_active":      entry["is_active"],
            "indexed":        info is not None and info["node_count"] > 0,
            "source_title":   info["title_raw"] if info else None,
            "source_root":    info["first_root"] if info else None,
            "version_label":  info["version_label"] if info else None,
            "pub_date":       info["pub_date"] if info else None,
            "amended_by":     info["amended_by"] if info else None,
            "node_count":     node_count,
            "harvest_key":       entry["harvest_key"],
            "harvester_enabled": harvest_enabled.get(entry["harvest_key"], False) if entry["harvest_key"] else False,
            "harvest_source_id": harvest_sources_map.get(entry["harvest_key"], {}).get("source_id") if entry["harvest_key"] else None,
        })
    return result


@router.post("/catalog", status_code=201)
async def create_catalog_entry(body: dict, db: AsyncSession = Depends(get_session)):
    """Create a new doc_sources entry."""
    required = {"id", "name", "short", "category_id", "domain_id"}
    missing = required - body.keys()
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing}")
    # Check uniqueness
    exists = await db.scalar(text("SELECT 1 FROM doc_sources WHERE id = :id"), {"id": body["id"]})
    if exists:
        raise HTTPException(status_code=409, detail=f"Document '{body['id']}' already exists")
    await db.execute(text("""
        INSERT INTO doc_sources (id, name, short, category_id, domain_id, description, easa_url,
                                 harvest_key, doc_title_pattern, is_active, sort_order)
        VALUES (:id, :name, :short, :category_id, :domain_id, :description, :easa_url,
                :harvest_key, :doc_title_pattern, TRUE,
                (SELECT COALESCE(MAX(sort_order), 0) + 1 FROM doc_sources))
    """), {
        "id":                body["id"],
        "name":              body["name"],
        "short":             body["short"],
        "category_id":       body["category_id"],
        "domain_id":         body["domain_id"],
        "description":       body.get("description", ""),
        "easa_url":          body.get("easa_url", ""),
        "harvest_key":       body.get("harvest_key") or None,
        "doc_title_pattern": body.get("doc_title_pattern") or None,
    })
    await db.commit()
    return {"ok": True, "id": body["id"]}


@router.patch("/catalog/{source_id}")
async def patch_catalog_entry(source_id: str, body: dict, db: AsyncSession = Depends(get_session)):
    """Update category, domain, is_active for a catalog entry."""
    allowed = {"category_id", "domain_id", "is_active", "description", "name", "short", "easa_url"}
    updates = {k: v for k, v in body.items() if k in allowed}
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    set_clause = ", ".join(f"{k} = :{k}" for k in updates)
    updates["source_id"] = source_id
    updates["updated_at"] = "NOW()"
    result = await db.execute(
        text(f"UPDATE doc_sources SET {set_clause}, updated_at = NOW() WHERE id = :source_id RETURNING id"),
        updates,
    )
    if not result.fetchone():
        raise HTTPException(status_code=404, detail=f"Catalog entry '{source_id}' not found")
    await db.commit()
    return {"ok": True}
