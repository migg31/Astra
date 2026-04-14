"""PGVector store for regulatory node chunks.

Each row in node_embeddings is one chunk (parent node or sub-chunk).
Public interface is identical to the former ChromaDB store so callers
need no changes: upsert / query / count.
"""
from __future__ import annotations

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

from backend.config import settings


def _conn() -> psycopg2.extensions.connection:
    conn = psycopg2.connect(settings.database_url_sync)
    register_vector(conn)
    return conn


_UPSERT_SQL = """
    INSERT INTO node_embeddings (
        chunk_id, parent_node_id, chunk_index, document, embedding,
        node_type, reference_code, title, hierarchy_path, content_hash,
        source_root, applicability_date, regulatory_source
    ) VALUES (
        %(chunk_id)s, %(parent_node_id)s, %(chunk_index)s, %(document)s, %(embedding)s,
        %(node_type)s, %(reference_code)s, %(title)s, %(hierarchy_path)s, %(content_hash)s,
        %(source_root)s, %(applicability_date)s, %(regulatory_source)s
    )
    ON CONFLICT (chunk_id) DO UPDATE SET
        parent_node_id    = EXCLUDED.parent_node_id,
        chunk_index       = EXCLUDED.chunk_index,
        document          = EXCLUDED.document,
        embedding         = EXCLUDED.embedding,
        node_type         = EXCLUDED.node_type,
        reference_code    = EXCLUDED.reference_code,
        title             = EXCLUDED.title,
        hierarchy_path    = EXCLUDED.hierarchy_path,
        content_hash      = EXCLUDED.content_hash,
        source_root       = EXCLUDED.source_root,
        applicability_date = EXCLUDED.applicability_date,
        regulatory_source  = EXCLUDED.regulatory_source
"""


def _row(node_id: str, embedding: list[float], document: str, metadata: dict) -> dict:
    return {
        "chunk_id":          node_id,
        "parent_node_id":    metadata.get("parent_node_id", node_id),
        "chunk_index":       int(metadata.get("chunk_index", 0)),
        "document":          document,
        "embedding":         embedding,
        "node_type":         metadata.get("node_type", ""),
        "reference_code":    metadata.get("reference_code", ""),
        "title":             metadata.get("title", ""),
        "hierarchy_path":    metadata.get("hierarchy_path", ""),
        "content_hash":      metadata.get("content_hash", ""),
        "source_root":       metadata.get("source_root", ""),
        "applicability_date": metadata.get("applicability_date", ""),
        "regulatory_source": metadata.get("regulatory_source", ""),
    }


def upsert(
    node_id: str,
    embedding: list[float],
    document: str,
    metadata: dict,
) -> None:
    """Insert or update a single chunk row."""
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, _row(node_id, embedding, document, metadata))
        conn.commit()


def upsert_batch(
    items: list[tuple[str, list[float], str, dict]],
    conn: "psycopg2.extensions.connection | None" = None,
) -> None:
    """Bulk upsert: items is a list of (node_id, embedding, document, metadata).

    Pass an open connection to reuse it across multiple batches (caller must commit).
    If conn is None, a new connection is opened and committed automatically.
    """
    rows = [_row(nid, emb, doc, meta) for nid, emb, doc, meta in items]
    own_conn = conn is None
    if own_conn:
        conn = _conn()
    try:
        with conn.cursor() as cur:
            psycopg2.extras.execute_batch(cur, _UPSERT_SQL, rows, page_size=100)
        if own_conn:
            conn.commit()
    finally:
        if own_conn:
            conn.close()


def query(
    embedding: list[float],
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Return top-n chunks by cosine similarity as list of {id, document, metadata, distance}.

    `where` supports a single equality filter: {"source_root": "easa-cs25"}.
    """
    filter_clause = ""
    filter_params: list = []

    if where:
        conditions = []
        for col, val in where.items():
            conditions.append(f"{col} = %s")
            filter_params.append(val)
        filter_clause = "WHERE " + " AND ".join(conditions)

    # Param order matches placeholder order in SQL:
    # 1. embedding  → SELECT (embedding <=> %s::vector)
    # 2. filter vals → WHERE col = %s ...
    # 3. n_results   → LIMIT %s
    params = [embedding] + filter_params + [n_results]

    sql = f"""
        SELECT chunk_id, document,
               node_type, reference_code, title, hierarchy_path, content_hash,
               source_root, applicability_date, regulatory_source,
               parent_node_id, chunk_index,
               (embedding <=> %s::vector) AS distance
        FROM node_embeddings
        {filter_clause}
        ORDER BY distance
        LIMIT %s
    """

    with _conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    hits = []
    for row in rows:
        hits.append({
            "id": row["chunk_id"],
            "document": row["document"],
            "distance": float(row["distance"]),
            "metadata": {
                "node_type":          row["node_type"],
                "reference_code":     row["reference_code"],
                "title":              row["title"],
                "hierarchy_path":     row["hierarchy_path"],
                "content_hash":       row["content_hash"],
                "source_root":        row["source_root"],
                "applicability_date": row["applicability_date"],
                "regulatory_source":  row["regulatory_source"],
                "parent_node_id":     row["parent_node_id"],
                "node_id":            row["parent_node_id"],
                "chunk_index":        str(row["chunk_index"]),
            },
        })
    return hits


def count() -> int:
    with _conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM node_embeddings")
            return cur.fetchone()[0]


def purge() -> dict[str, int]:
    """Truncate all indexed data tables. Preserves catalog and harvest source config."""
    tables = [
        "node_embeddings",
        "regulatory_nodes",
        "harvest_documents",
        "harvest_document_versions",
        "document_harvest_runs",
        "regulatory_node_versions",
        "regulatory_changes",
        "regulatory_edges",
    ]
    counts: dict[str, int] = {}
    with _conn() as conn:
        with conn.cursor() as cur:
            for table in tables:
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                counts[table] = cur.fetchone()[0]
            cur.execute(
                "TRUNCATE TABLE node_embeddings, regulatory_nodes, harvest_documents, "
                "harvest_document_versions, document_harvest_runs, regulatory_node_versions, "
                "regulatory_changes, regulatory_edges RESTART IDENTITY CASCADE"
            )
        conn.commit()
    return counts
