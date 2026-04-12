"""CLI: generate embeddings for all regulatory nodes and store in ChromaDB.

Run with:
    python -m uv run python -m backend.rag.ingest_embeddings

Safe to re-run: uses upsert, so existing embeddings are updated if the
content_hash has changed.
"""
from __future__ import annotations

import sys

import psycopg2

from backend.config import settings
from backend.rag.embedder import embed_batch
from backend.rag.store import upsert, count


def _fetch_nodes(cur) -> list[dict]:
    cur.execute(
        """
        SELECT rn.node_id::text, rn.node_type, rn.reference_code, rn.title,
               rn.content_text, rn.content_hash, rn.hierarchy_path,
               rn.regulatory_source, rn.applicability_date,
               COALESCE(hd.external_id, '') AS source_root
        FROM regulatory_nodes rn
        LEFT JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
        WHERE rn.node_type != 'GROUP'
          AND rn.content_text IS NOT NULL
          AND rn.content_text != ''
        ORDER BY rn.hierarchy_path, rn.reference_code
        """
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


MAX_EMBED_CHARS = 2000  # safe limit for nomic-embed-text (~8192 tokens, 4 chars/token avg)


def _build_document(node: dict) -> str:
    """Text fed to the embedding model — reference + title + body (truncated)."""
    parts = [node["reference_code"]]
    if node["title"]:
        parts.append(node["title"])
    body = node["content_text"] or ""
    parts.append(body)
    doc = "\n\n".join(parts)
    return doc[:MAX_EMBED_CHARS]


def main(on_progress=None) -> int:
    _emit = on_progress or print
    _emit("[embed] connecting to database …")
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            nodes = _fetch_nodes(cur)

    total = len(nodes)
    _emit(f"[embed] {total} nodes to embed")

    # Batch in groups of 32 to avoid oversized requests.
    BATCH = 32
    embedded = 0
    skipped = 0
    for i in range(0, total, BATCH):
        batch = nodes[i : i + BATCH]
        docs = [_build_document(n) for n in batch]
        try:
            embeddings = embed_batch(docs)
            for node, emb in zip(batch, embeddings):
                upsert(
                    node_id=node["node_id"],
                    embedding=emb,
                    document=_build_document(node),
                    metadata={
                        "node_type":       node["node_type"],
                        "reference_code":  node["reference_code"],
                        "title":           node["title"] or "",
                        "hierarchy_path":  node["hierarchy_path"],
                        "content_hash":    node["content_hash"],
                        "source_root":     node["source_root"],
                    },
                )
        except Exception:
            for node, doc in zip(batch, docs):
                try:
                    emb = embed_batch([doc])[0]
                    upsert(
                        node_id=node["node_id"],
                        embedding=emb,
                        document=doc,
                        metadata={
                            "node_type":       node["node_type"],
                            "reference_code":  node["reference_code"],
                            "title":           node["title"] or "",
                            "hierarchy_path":  node["hierarchy_path"],
                            "content_hash":    node["content_hash"],
                            "source_root":     node["source_root"],
                        },
                    )
                except Exception:
                    _emit(f"[embed] SKIP {node['reference_code']!r} — exceeds context length")
                    skipped += 1
        embedded += len(batch)
        pct = round(embedded / total * 100) if total else 100
        _emit(f"[embed:progress] {embedded}/{total} {pct}")

    if skipped:
        _emit(f"[embed] warning — {skipped} nodes skipped (context too long)")

    _emit(f"[embed] done — ChromaDB collection now has {count()} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
