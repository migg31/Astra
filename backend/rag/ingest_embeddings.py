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
from backend.rag.store import upsert_batch, count
from backend.rag import store as _store


def _fetch_nodes(cur) -> list[dict]:
    cur.execute(
        """
        SELECT rn.node_id::text, rn.node_type, rn.reference_code, rn.title,
               rn.content_text, rn.content_hash, rn.hierarchy_path,
               rn.regulatory_source, rn.applicability_date,
               COALESCE(hd.external_id, '') AS source_root
        FROM regulatory_nodes rn
        JOIN harvest_documents hd ON hd.doc_id = rn.source_doc_id
        WHERE rn.node_type != 'GROUP'
          AND rn.content_text IS NOT NULL
          AND rn.content_text != ''
          AND hd.is_latest = true
        ORDER BY rn.hierarchy_path, rn.reference_code
        """
    )
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


CHUNK_SIZE = 1200       # target chars per child chunk (~300 tokens for nomic-embed-text)
CHUNK_OVERLAP = 150    # overlap to preserve context across chunk boundaries
_SPLIT_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def _recursive_split(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text recursively on paragraph/sentence/word boundaries.

    Tries each separator in order; falls back to the next if chunks are still too large.
    """
    def _split_on(sep: str, remaining: str) -> list[str]:
        if sep == "":
            return [remaining[i : i + size] for i in range(0, len(remaining), size - overlap)]
        parts = remaining.split(sep)
        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                current = part
        if current:
            chunks.append(current)
        return chunks

    chunks: list[str] = [text]
    for sep in _SPLIT_SEPARATORS:
        next_chunks: list[str] = []
        for chunk in chunks:
            if len(chunk) <= size:
                next_chunks.append(chunk)
            else:
                next_chunks.extend(_split_on(sep, chunk))
        chunks = next_chunks
        if all(len(c) <= size for c in chunks):
            break

    # Add overlap: prepend tail of previous chunk to next
    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append(tail + chunks[i])
        chunks = overlapped

    return [c.strip() for c in chunks if c.strip()]


def _breadcrumb_prefix(node: dict) -> str:
    """Build the breadcrumb header: [source_root] > [hierarchy_path] > [reference_code]."""
    parts = []
    if node.get("source_root"):
        parts.append(node["source_root"])
    if node.get("hierarchy_path"):
        parts.append(node["hierarchy_path"])
    parts.append(node["reference_code"])
    header = " > ".join(parts)
    if node.get("title"):
        header += f" — {node['title']}"
    return header


def _build_chunks(node: dict) -> list[str]:
    """Return a list of embedding-ready strings for a node (one or more chunks).

    Each chunk carries the breadcrumb prefix so the vector encodes source identity.
    """
    prefix = _breadcrumb_prefix(node)
    body = node["content_text"] or ""
    body_chunks = _recursive_split(body)
    return [f"{prefix}\n\n{chunk}" for chunk in body_chunks]


def main(on_progress=None) -> int:
    _emit = on_progress or print
    _emit("[embed] connecting to database …")
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            nodes = _fetch_nodes(cur)

    total = len(nodes)
    _emit(f"[embed] {total} nodes to embed")

    # Expand nodes into (node, chunk_index, chunk_text) triples before batching.
    # Each chunk gets a unique id: "{node_id}__c{index}" (chunk 0 keeps the bare node_id).
    all_chunks: list[tuple[dict, int, str]] = []
    for node in nodes:
        for idx, chunk_text in enumerate(_build_chunks(node)):
            all_chunks.append((node, idx, chunk_text))

    total_chunks = len(all_chunks)
    _emit(f"[embed] {total} nodes → {total_chunks} chunks to embed")

    # Single persistent connection for all upserts — much faster than one conn/chunk.
    pg_conn = _store._conn()
    try:
        # Batch in groups of 32 to avoid oversized embedding requests.
        BATCH = 32
        embedded = 0
        skipped = 0
        for i in range(0, total_chunks, BATCH):
            batch = all_chunks[i : i + BATCH]
            docs = [chunk_text for _, _, chunk_text in batch]
            try:
                embeddings = embed_batch(docs)
                upsert_items = []
                for (node, idx, chunk_text), emb in zip(batch, embeddings):
                    chunk_id = node["node_id"] if idx == 0 else f"{node['node_id']}__c{idx}"
                    upsert_items.append((
                        chunk_id,
                        emb,
                        chunk_text,
                        {
                            "node_type":          node["node_type"],
                            "reference_code":     node["reference_code"],
                            "title":              node["title"] or "",
                            "hierarchy_path":     node["hierarchy_path"],
                            "content_hash":       node["content_hash"],
                            "source_root":        node["source_root"],
                            "applicability_date": node["applicability_date"] or "",
                            "regulatory_source":  node["regulatory_source"] or "",
                            "parent_node_id":     node["node_id"],
                            "chunk_index":        str(idx),
                        },
                    ))
                upsert_batch(upsert_items, conn=pg_conn)
            except Exception:
                for node, idx, chunk_text in batch:
                    try:
                        emb = embed_batch([chunk_text])[0]
                        chunk_id = node["node_id"] if idx == 0 else f"{node['node_id']}__c{idx}"
                        upsert_batch([
                            (chunk_id, emb, chunk_text, {
                                "node_type":          node["node_type"],
                                "reference_code":     node["reference_code"],
                                "title":              node["title"] or "",
                                "hierarchy_path":     node["hierarchy_path"],
                                "content_hash":       node["content_hash"],
                                "source_root":        node["source_root"],
                                "applicability_date": node["applicability_date"] or "",
                                "regulatory_source":  node["regulatory_source"] or "",
                                "parent_node_id":     node["node_id"],
                                "chunk_index":        str(idx),
                            })
                        ], conn=pg_conn)
                    except Exception:
                        _emit(f"[embed] SKIP {node['reference_code']!r} chunk {idx} — exceeds context length")
                        skipped += 1
            embedded += len(batch)
            pct = round(embedded / total_chunks * 100) if total_chunks else 100
            _emit(f"[embed:progress] {embedded}/{total_chunks} {pct}")
        pg_conn.commit()
    finally:
        pg_conn.close()

    if skipped:
        _emit(f"[embed] warning — {skipped} nodes skipped (context too long)")

    _emit(f"[embed] done — pgvector table now has {count()} chunks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
