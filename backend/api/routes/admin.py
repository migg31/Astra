from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.connection import get_session
from backend.rag.store import count as count_embeddings, _CHROMA_PATH
from backend.harvest.ingest import (
    ingest, 
    fetch_part21_xml, 
    PART21_XML_ZIP_URL, 
    SOURCE_NAME, 
    SOURCE_FREQUENCY, 
    SOURCE_FORMAT
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
    
    return SystemConfig(
        harvester_source_url=PART21_XML_ZIP_URL,
        harvester_name=SOURCE_NAME,
        harvester_frequency=SOURCE_FREQUENCY,
        harvester_format=SOURCE_FORMAT,
        data_directory=str(Path("data").resolve()),
        db_host=db_url.hostname or "localhost",
        ollama_base_url=OLLAMA_BASE_URL
    )

@router.get("/harvester/status", response_model=IngestionStatus)
async def get_harvester_status():
    """Get the current state of the ingestion process."""
    return _status

async def _run_harvester_task():
    """Background task to run the full ingestion and embedding pipeline."""
    global _status
    async with _lock:
        _status.is_running = True
        _status.error = None
        try:
            # 1. Fetch & Ingest into Postgres
            # We use a temporary directory for downloads
            data_dir = Path("data")
            data_dir.mkdir(parents=True, exist_ok=True)
            
            # Fetch
            fetched = fetch_part21_xml(data_dir)
            
            # Ingest (sync call, but in thread pool via run_in_executor if needed)
            # For now, we run it directly in the background task (which is already a thread for sync def)
            # but since this is an 'async def' task, we should use run_in_executor for sync blocks.
            loop = asyncio.get_running_loop()
            report = await loop.run_in_executor(
                None, 
                lambda: ingest(fetched.path, source_url=fetched.url, content_hash=fetched.content_hash)
            )
            
            # 2. Run Embedding Pipeline
            await loop.run_in_executor(None, run_embedding_pipeline)
            
            _status.last_report = report
            _status.last_run_at = datetime.now(timezone.utc)
        except Exception as e:
            _status.error = str(e)
        finally:
            _status.is_running = False

@router.post("/harvester/run")
async def start_harvester(background_tasks: BackgroundTasks):
    """Trigger the ingestion process in the background."""
    if _status.is_running:
        raise HTTPException(status_code=400, detail="Harvester is already running")
    
    background_tasks.add_task(_run_harvester_task)
    return {"message": "Harvester started"}
