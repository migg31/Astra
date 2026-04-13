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
from backend.rag.responder import answer, expand_query, rerank
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
    n_sources: int = Field(10, ge=1, le=20)
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


class CitedNode(BaseModel):
    node_id: str
    reference_code: str
    node_type: str
    hierarchy_path: str = ""


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceNode]
    question: str
    cited_node_ids: list[str] = []
    cited_nodes: list[CitedNode] = []


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


def _build_tsquery(question: str) -> str | None:
    """Build the best tsquery for a natural-language question.

    Priority:
      1. websearch_to_tsquery  — supports phrases ("air data"), AND, OR, negation
      2. plainto_tsquery       — plain AND of all words (fallback)
    Returns the SQL function call string to embed, or None if question is empty.
    """
    q = question.strip()
    return q if q else None


_FTS_SQL = """
    SELECT rn.node_id::text, rn.node_type, rn.reference_code, rn.title,
           rn.content_text, rn.content_hash, rn.hierarchy_path,
           GREATEST(
               ts_rank_cd(
                   to_tsvector('english', COALESCE(rn.content_text, '')),
                   websearch_to_tsquery('english', %(q)s)
               ),
               ts_rank_cd(
                   to_tsvector('english', COALESCE(rn.title, '')),
                   websearch_to_tsquery('english', %(q)s)
               )
           ) AS rank
    FROM regulatory_nodes rn
    JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
    WHERE {doc_filter}
      AND rn.node_type != 'GROUP'
      AND (
          to_tsvector('english', COALESCE(rn.content_text, ''))
              @@ websearch_to_tsquery('english', %(q)s)
          OR to_tsvector('english', COALESCE(rn.title, ''))
              @@ websearch_to_tsquery('english', %(q)s)
      )
    ORDER BY rank DESC
    LIMIT %(limit)s
"""


_FTS_STRIP_RE = re.compile(
    r"\b(CS[\s\-]?\d+|Part[\s\-]?\d+[A-Z]?|Part[\s\-]?[A-Z]+|EASA|how|what|when|where|which"
    r"|does|the|and|for|are|that|this|with|from|have|about|explain|describe|considered|in)\b",
    re.IGNORECASE,
)


def _fts_query(question: str) -> str:
    """Strip document names and stopwords, return clean query for websearch_to_tsquery."""
    cleaned = _FTS_STRIP_RE.sub(" ", question)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or question


def _run_fts(question: str, doc_filter_sql: str, filter_params: dict, limit: int) -> list[dict]:
    """Execute FTS query and return formatted hits.

    Uses named params: %(q)s for the search query, %(limit)s for LIMIT,
    plus any extra named params in filter_params for the WHERE clause.
    """
    q = _fts_query(question)
    if not q:
        return []
    full_params = {"q": q, "limit": limit, **filter_params}
    sql = _FTS_SQL.format(doc_filter=doc_filter_sql)
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, full_params)
                rows = cur.fetchall()
            except Exception:
                return []
    hits = []
    for row in rows:
        node_id, node_type, ref, title, content_text, content_hash, hierarchy, _rank = row
        hits.append({
            "id": node_id,
            "document": f"{ref}\n\n{title or ''}\n\n{content_text[:3200]}",
            "metadata": {
                "node_id": node_id,
                "parent_node_id": node_id,
                "node_type": node_type,
                "reference_code": ref,
                "title": title or "",
                "hierarchy_path": hierarchy,
                "content_hash": content_hash,
            },
            "distance": 0.05,
        })
    return hits


def _fetch_by_doc_fulltext(external_id: str, question: str, limit: int = 3) -> list[dict]:
    """FTS within a specific document."""
    return _run_fts(
        question,
        doc_filter_sql="hd.external_id = %(ext_id)s",
        filter_params={"ext_id": external_id},
        limit=limit,
    )


def _fetch_fts_global(question: str, limit: int = 6) -> list[dict]:
    """FTS across all documents — used when no source_filter and no codes detected."""
    return _run_fts(
        question,
        doc_filter_sql="TRUE",
        filter_params={},
        limit=limit,
    )


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
            "document": f"{ref}\n\n{title or ''}\n\n{content_text[:3200]}",
            "metadata": {
                "node_id": node_id,
                "parent_node_id": node_id,
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

    # 1. Extract specific article codes mentioned in the question.
    mentioned_codes = list(set(_ARTICLE_RE.findall(req.question)))

    # 1b. If no codes in question, use LLM to suggest probable codes (query expansion)
    if not mentioned_codes:
        mentioned_codes = expand_query(req.question)

    # 2. Fetch those nodes directly (exact match — highest relevance)
    keyword_hits_raw = _fetch_by_codes(mentioned_codes, source_filter=req.source_filter)
    # Track parent_node_ids of exact hits to exclude their chunks from vector results
    def _parent_id(h: dict) -> str:
        return h["metadata"].get("parent_node_id") or h["id"]
    # Deduplicate keyword hits: keep only first variant per article base code
    # (avoids AMC 25.1323(d) + (e) + (h) all flooding the list)
    _seen_kw: set[str] = set()
    keyword_hits: list[dict] = []
    for h in keyword_hits_raw:
        pid = _parent_id(h)
        if pid not in _seen_kw:
            _seen_kw.add(pid)
            keyword_hits.append(h)
    keyword_ids = set(_seen_kw)

    # 2b. FTS injection: find relevant articles via full-text search.
    #     - If source_filter or doc mentioned → search within that document
    #     - If neither → global FTS across all documents
    #     Boost limit when no article codes detected (broader coverage needed).
    doc_hits: list[dict] = []
    mentioned_docs = _resolve_doc_mentions(req.question)
    fts_limit = 3 if mentioned_codes else 8

    # Build the list of docs to run per-doc FTS on
    fts_docs: list[str] = []
    if req.source_filter:
        fts_docs = [req.source_filter]
    elif mentioned_docs:
        fts_docs = mentioned_docs

    if fts_docs:
        for ext_id in fts_docs:
            for h in _fetch_by_doc_fulltext(ext_id, req.question, limit=fts_limit):
                if _parent_id(h) not in keyword_ids:
                    doc_hits.append(h)
                    keyword_ids.add(_parent_id(h))
    elif not mentioned_codes:
        # No doc filter, no codes → global FTS fallback
        for h in _fetch_fts_global(req.question, limit=fts_limit):
            if _parent_id(h) not in keyword_ids:
                doc_hits.append(h)
                keyword_ids.add(_parent_id(h))

    # 3. Vector search — optionally filtered by source_root via pgvector metadata
    #    If no explicit source_filter, auto-detect from doc mentions (single doc only).
    n_vector = max(req.n_sources * 2, 20)  # fetch more for RRF to work well
    q_embedding = embed(req.question)
    effective_source_filter = req.source_filter
    if not effective_source_filter and len(mentioned_docs) == 1:
        effective_source_filter = mentioned_docs[0]
    pg_where = {"source_root": effective_source_filter} if effective_source_filter else None
    try:
        vector_hits = [h for h in query(q_embedding, n_results=n_vector, where=pg_where)
                       if _parent_id(h) not in keyword_ids]
    except Exception:
        vector_hits = [h for h in query(q_embedding, n_results=n_vector)
                       if _parent_id(h) not in keyword_ids]

    # 4. RRF fusion of FTS hits + vector hits (keyword exact-match pinned at top)
    #    Score = 1/(k + rank_fts) + 1/(k + rank_vector)  with k=60 (standard)
    n_final = req.n_sources
    RRF_K = 60

    # Build parent_id → best hit map for dedup within each list
    def _best_by_parent(hits_list: list[dict]) -> dict[str, dict]:
        seen: dict[str, dict] = {}
        for h in hits_list:
            pid = _parent_id(h)
            if pid not in seen or h["distance"] < seen[pid]["distance"]:
                seen[pid] = h
        return seen

    fts_map  = _best_by_parent(doc_hits)
    vec_map  = _best_by_parent(vector_hits)
    all_pids = set(fts_map) | set(vec_map)

    rrf_scores: dict[str, float] = {}
    for rank, pid in enumerate(fts_map):   # fts_map is ordered by ts_rank DESC
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + 1.0 / (RRF_K + rank)
    for rank, pid in enumerate(vec_map):   # vec_map is ordered by cosine distance ASC
        rrf_scores[pid] = rrf_scores.get(pid, 0.0) + 1.0 / (RRF_K + rank)

    # Merge: pick best hit per parent, sort by RRF score desc
    # Keep original distance intact for display — store rrf_score in metadata only
    merged_hits = []
    for pid in sorted(all_pids, key=lambda p: rrf_scores.get(p, 0.0), reverse=True):
        h = dict(fts_map.get(pid) or vec_map[pid])  # shallow copy
        h["rrf_score"] = rrf_scores[pid]
        merged_hits.append(h)

    # Keyword exact-match hits pinned at front, not subject to RRF
    candidate_hits = keyword_hits + merged_hits

    if not candidate_hits:
        raise HTTPException(status_code=404, detail="No relevant regulatory content found.")

    # 5. Rerank top candidates with LLM — use full RRF-sorted pool (no pre-truncation)
    if len(candidate_hits) > n_final:
        rrf_pool = merged_hits[:max(n_final * 2, 12)]
        rrf_reranked = rerank(req.question, rrf_pool)
        hits = keyword_hits + rrf_reranked
    else:
        hits = candidate_hits

    # 6. Generate answer — use full hits (before cap) so cited articles are in context
    generated, cited_node_ids = answer(req.question, hits)

    # Build cited_nodes lookup from full hits (before cap)
    hits_by_id = {h["metadata"].get("node_id") or h["id"]: h for h in hits}
    cited_nodes: list[CitedNode] = []
    for nid in cited_node_ids:
        h = hits_by_id.get(nid)
        if h:
            m = h["metadata"]
            cited_nodes.append(CitedNode(
                node_id=nid,
                reference_code=m.get("reference_code", nid),
                node_type=m.get("node_type", "CS"),
                hierarchy_path=m.get("hierarchy_path", ""),
            ))

    # 7. Build source list — cap to n_final, deduplicate by parent_node_id and base ref code
    hits = hits[:n_final]
    seen_parents: set[str] = set()
    seen_base_refs: set[str] = set()
    sources: list[SourceNode] = []
    for h in hits:
        meta = h["metadata"]
        parent_id = meta.get("parent_node_id") or h["id"]
        ref = meta["reference_code"]
        base_ref = re.sub(r"\s*\([^)]*\)\s*$", "", ref).strip()
        if parent_id in seen_parents or base_ref in seen_base_refs:
            continue
        seen_parents.add(parent_id)
        seen_base_refs.add(base_ref)
        sources.append(SourceNode(
            node_id=parent_id,
            reference_code=base_ref if base_ref != ref else ref,
            title=meta.get("title", ""),
            node_type=meta["node_type"],
            hierarchy_path=meta.get("hierarchy_path", ""),
            score=round(1 - h["distance"], 3),
        ))

    return AskResponse(answer=generated, sources=sources, question=req.question, cited_node_ids=cited_node_ids, cited_nodes=cited_nodes)
