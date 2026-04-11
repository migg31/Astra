"""POST /api/ask — RAG-based regulatory Q&A endpoint.

Hybrid retrieval:
  1. Vector search (semantic similarity via nomic-embed-text)
  2. Keyword injection: any 21.X.XX article code mentioned in the question
     is fetched directly from the DB and added to the context — this is the
     highest-signal hint and bypasses the French/English embedding gap.
"""
from __future__ import annotations

import re

import psycopg2
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config import settings
from backend.rag.embedder import embed
from backend.rag.responder import answer
from backend.rag.store import count, query

router = APIRouter(prefix="/api/ask", tags=["ask"])

_ARTICLE_RE = re.compile(r"21\.[A-Z]\.\d+[A-Z]?")


class AskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    n_sources: int = Field(6, ge=1, le=12)


class SourceNode(BaseModel):
    node_id: str
    reference_code: str
    title: str
    node_type: str
    hierarchy_path: str
    score: float


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceNode]
    question: str


def _fetch_by_codes(codes: list[str]) -> list[dict]:
    """Fetch all nodes whose reference_code contains one of the article codes."""
    if not codes:
        return []
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(codes))
            cur.execute(
                f"""
                SELECT node_id::text, node_type, reference_code, title,
                       content_text, content_hash, hierarchy_path
                FROM regulatory_nodes
                WHERE reference_code = ANY(ARRAY[{placeholders}])
                   OR reference_code ~* %s
                """,
                codes + ["|".join(re.escape(c) for c in codes)],
            )
            rows = cur.fetchall()
    hits = []
    for row in rows:
        node_id, node_type, ref, title, content_text, content_hash, hierarchy = row
        hits.append({
            "id": node_id,
            "document": f"{ref}\n\n{title or ''}\n\n{content_text[:6000]}",
            "metadata": {
                "node_type": node_type,
                "reference_code": ref,
                "title": title or "",
                "hierarchy_path": hierarchy,
                "content_hash": content_hash,
            },
            "distance": 0.0,  # exact match — top relevance
        })
    return hits


@router.post("", response_model=AskResponse)
async def ask(req: AskRequest) -> AskResponse:
    if count() == 0:
        raise HTTPException(
            status_code=503,
            detail="Vector store is empty. Run `python -m backend.rag.ingest_embeddings` first.",
        )

    # 1. Extract article codes mentioned in the question
    mentioned_codes = list(set(_ARTICLE_RE.findall(req.question)))

    # 2. Fetch those nodes directly (exact match — highest relevance)
    keyword_hits = _fetch_by_codes(mentioned_codes)
    keyword_ids = {h["id"] for h in keyword_hits}

    # 3. Vector search for the rest
    n_vector = max(req.n_sources, req.n_sources + len(keyword_hits))
    q_embedding = embed(req.question)
    vector_hits = [h for h in query(q_embedding, n_results=n_vector)
                   if h["id"] not in keyword_ids]

    # 4. Merge: keyword hits first, then vector hits up to n_sources total
    hits = keyword_hits + vector_hits
    hits = hits[:req.n_sources + len(keyword_hits)]  # keep all keyword hits + fill with vector

    if not hits:
        raise HTTPException(status_code=404, detail="No relevant regulatory content found.")

    # 5. Generate answer
    generated = answer(req.question, hits)

    # 6. Build source list
    sources = [
        SourceNode(
            node_id=h["id"],
            reference_code=h["metadata"]["reference_code"],
            title=h["metadata"].get("title", ""),
            node_type=h["metadata"]["node_type"],
            hierarchy_path=h["metadata"].get("hierarchy_path", ""),
            score=round(1 - h["distance"], 3),
        )
        for h in hits
    ]

    return AskResponse(answer=generated, sources=sources, question=req.question)
