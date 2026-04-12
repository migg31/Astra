"""POST /api/ask — RAG-based regulatory Q&A endpoint.

Hybrid retrieval:
  1. Vector search (semantic similarity via nomic-embed-text)
  2. Keyword injection: any EASA article code mentioned in the question
     is fetched directly from the DB and added to the context — this is the
     highest-signal hint and bypasses the French/English embedding gap.

Optional `source_filter` restricts retrieval to a specific indexed document
(e.g. "cs-25", "part21"). If omitted, all indexed documents are searched.
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

# Matches specific EASA article codes: 21.A.91, M.A.302, 25.1309, ACNS.B.GEN.1005
_ARTICLE_RE = re.compile(
    r"\b(?:[A-Z]{1,6}\.(?:[A-Z]\.)?\d+[A-Z]?|\d{2,3}\.\d+[A-Z]?)\b"
)

# Maps document name mentions → external_id in harvest_documents
_DOC_NAME_RE = re.compile(
    r"\b(CS[\s\-]?25|CS[\s\-]?ACNS|CS[\s\-]?23|CS[\s\-]?27|CS[\s\-]?29"
    r"|Part[\s\-]?21|Part[\s\-]?26|Part[\s\-]?M\b|Part[\s\-]?145\b|Part[\s\-]?66\b"
    r"|Part[\s\-]?CAT|Part[\s\-]?ORO|Part[\s\-]?NCC|Part[\s\-]?SPO"
    r"|Part[\s\-]?ADR|Part[\s\-]?CAMO|Part[\s\-]?CAO)\b",
    re.IGNORECASE,
)

_DOC_NAME_TO_EXTERNAL_ID: dict[str, str] = {
    "cs25": "easa-cs25",   "cs-25": "easa-cs25",
    "cs23": "easa-cs23",   "cs-23": "easa-cs23",
    "cs27": "easa-cs27",   "cs-27": "easa-cs27",
    "cs29": "easa-cs29",   "cs-29": "easa-cs29",
    "csacns": "easa-csacns", "cs-acns": "easa-csacns",
    "part21": "easa-part21", "part-21": "easa-part21",
    "part26": "easa-part26", "part-26": "easa-part26",
    "partm": "easa-airworthiness", "part-m": "easa-airworthiness",
    "part145": "easa-airworthiness", "part-145": "easa-airworthiness",
    "part66": "easa-airworthiness",  "part-66": "easa-airworthiness",
    "partcat": "easa-ops",  "part-cat": "easa-ops",
    "partoro": "easa-ops",  "part-oro": "easa-ops",
    "partncc": "easa-ops",  "part-ncc": "easa-ops",
    "partspo": "easa-ops",  "part-spo": "easa-ops",
    "partadr": "easa-aerodromes", "part-adr": "easa-aerodromes",
    "partcamo": "easa-airworthiness", "part-camo": "easa-airworthiness",
}


class AskRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    n_sources: int = Field(6, ge=1, le=12)
    source_filter: str | None = Field(
        None,
        description="Optional: restrict search to a specific source root (e.g. 'cs-25', 'part21').",
    )


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


def _resolve_doc_mentions(question: str) -> list[str]:
    """Return external_ids for any document names mentioned in the question (e.g. 'CS 25' → 'easa-cs25')."""
    matches = _DOC_NAME_RE.findall(question)
    ids: list[str] = []
    for m in matches:
        key = re.sub(r"\s+", "", m).lower()  # "CS 25" → "cs25", "Part-21" → "part-21"
        ext_id = _DOC_NAME_TO_EXTERNAL_ID.get(key)
        if ext_id and ext_id not in ids:
            ids.append(ext_id)
    return ids


def _fetch_by_doc_fulltext(external_id: str, question: str, limit: int = 3) -> list[dict]:
    """Full-text search within a specific document to inject relevant articles when no
    specific article code was mentioned. Uses PostgreSQL ts_rank for relevance."""
    keywords = " | ".join(
        w for w in re.sub(r"[^\w\s]", " ", question).split()
        if len(w) > 3 and w.lower() not in {
            "what", "when", "where", "which", "how", "does", "the", "and",
            "for", "are", "that", "this", "with", "from", "have", "about",
        }
    )
    if not keywords:
        return []
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rn.node_id::text, rn.node_type, rn.reference_code, rn.title,
                       rn.content_text, rn.content_hash, rn.hierarchy_path,
                       ts_rank(to_tsvector('english', rn.content_text),
                               to_tsquery('english', %s)) AS rank
                FROM regulatory_nodes rn
                JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
                WHERE hd.external_id = %s
                  AND rn.node_type != 'GROUP'
                  AND to_tsvector('english', rn.content_text) @@ to_tsquery('english', %s)
                ORDER BY rank DESC
                LIMIT %s
                """,
                (keywords, external_id, keywords, limit),
            )
            rows = cur.fetchall()
    hits = []
    for row in rows:
        node_id, node_type, ref, title, content_text, content_hash, hierarchy, _rank = row
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
            "distance": 0.05,  # near-exact — high relevance but below keyword exact match
        })
    return hits


def _fetch_by_codes(codes: list[str], source_filter: str | None = None) -> list[dict]:
    """Fetch all nodes whose reference_code matches one of the article codes."""
    if not codes:
        return []
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            placeholders = ",".join(["%s"] * len(codes))
            source_clause = ""
            params: list = codes + ["|".join(re.escape(c) for c in codes)]
            if source_filter:
                source_clause = """
                AND EXISTS (
                    SELECT 1 FROM harvest_documents hd
                    WHERE hd.doc_id = rn.source_doc_id
                      AND hd.external_id = %s
                )"""
                params.append(source_filter)
            cur.execute(
                f"""
                SELECT rn.node_id::text, rn.node_type, rn.reference_code, rn.title,
                       rn.content_text, rn.content_hash, rn.hierarchy_path
                FROM regulatory_nodes rn
                WHERE (rn.reference_code = ANY(ARRAY[{placeholders}])
                   OR rn.reference_code ~* %s)
                {source_clause}
                """,
                params,
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

    # 1. Extract specific article codes mentioned in the question
    mentioned_codes = list(set(_ARTICLE_RE.findall(req.question)))

    # 2. Fetch those nodes directly (exact match — highest relevance)
    keyword_hits = _fetch_by_codes(mentioned_codes, source_filter=req.source_filter)
    keyword_ids = {h["id"] for h in keyword_hits}

    # 2b. Doc-level fulltext injection: when question names a document ("CS 25", "Part 21")
    #     but no specific article code — inject top relevant articles from that document.
    doc_hits: list[dict] = []
    mentioned_docs = _resolve_doc_mentions(req.question)
    # If source_filter is active, only inject for that document
    if req.source_filter:
        mentioned_docs = [req.source_filter] if req.source_filter in mentioned_docs or not mentioned_docs else []
    for ext_id in mentioned_docs:
        for h in _fetch_by_doc_fulltext(ext_id, req.question, limit=3):
            if h["id"] not in keyword_ids:
                doc_hits.append(h)
                keyword_ids.add(h["id"])

    # 3. Vector search — optionally filtered by source_doc_id via ChromaDB metadata
    n_vector = max(req.n_sources, req.n_sources + len(keyword_hits))
    q_embedding = embed(req.question)
    chroma_where = {"source_root": req.source_filter} if req.source_filter else None
    try:
        vector_hits = [h for h in query(q_embedding, n_results=n_vector, where=chroma_where)
                       if h["id"] not in keyword_ids]
    except Exception:
        # ChromaDB where filter fails if field absent in metadata — fall back to unfiltered
        vector_hits = [h for h in query(q_embedding, n_results=n_vector)
                       if h["id"] not in keyword_ids]

    # 4. Merge: keyword hits first, then doc fulltext hits, then vector hits
    hits = keyword_hits + doc_hits + vector_hits
    hits = hits[:req.n_sources + len(keyword_hits) + len(doc_hits)]

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
