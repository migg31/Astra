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
        SELECT node_id::text, node_type, reference_code, title,
               content_text, content_hash, hierarchy_path,
               regulatory_source, applicability_date
        FROM regulatory_nodes
        WHERE node_type != 'GROUP'
          AND content_text IS NOT NULL
          AND content_text != ''
        ORDER BY hierarchy_path, reference_code
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


def main() -> int:
    print("[embed] connecting to database …")
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            nodes = _fetch_nodes(cur)

    print(f"[embed] {len(nodes)} nodes to embed")

    # Batch in groups of 32 to avoid oversized requests.
    BATCH = 32
    embedded = 0
    skipped = 0
    for i in range(0, len(nodes), BATCH):
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
                    },
                )
        except Exception:
            # Batch failed — retry each node individually
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
                        },
                    )
                except Exception:
                    print(f"[embed] SKIP {node['reference_code']!r} — exceeds context length")
                    skipped += 1
        embedded += len(batch)
        print(f"[embed] {embedded}/{len(nodes)} …")

    if skipped:
        print(f"[embed] warning — {skipped} nodes skipped (context too long)")

    print(f"[embed] done — ChromaDB collection now has {count()} documents")
    return 0


if __name__ == "__main__":
    sys.exit(main())
