"""ChromaDB vector store for regulatory nodes.

Each document in the collection is one regulatory node, identified by its
node_id. Metadata fields allow filtering without a DB round-trip.
"""
from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings

# Persist embeddings alongside the project data so they survive restarts.
_CHROMA_PATH = Path(__file__).resolve().parents[2] / "data" / "chroma"

_client: chromadb.PersistentClient | None = None
_collection: chromadb.Collection | None = None

COLLECTION_NAME = "regulatory_nodes"


def get_collection() -> chromadb.Collection:
    global _client, _collection
    if _collection is None:
        _CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=str(_CHROMA_PATH),
            settings=Settings(anonymized_telemetry=False),
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def upsert(
    node_id: str,
    embedding: list[float],
    document: str,
    metadata: dict,
) -> None:
    get_collection().upsert(
        ids=[node_id],
        embeddings=[embedding],
        documents=[document],
        metadatas=[metadata],
    )


def query(
    embedding: list[float],
    n_results: int = 5,
    where: dict | None = None,
) -> list[dict]:
    """Return top-n results as list of {id, document, metadata, distance}."""
    kwargs: dict = {"query_embeddings": [embedding], "n_results": n_results}
    if where:
        kwargs["where"] = where
    result = get_collection().query(
        **kwargs,
        include=["documents", "metadatas", "distances"],
    )
    hits = []
    for i, node_id in enumerate(result["ids"][0]):
        hits.append(
            {
                "id": node_id,
                "document": result["documents"][0][i],
                "metadata": result["metadatas"][0][i],
                "distance": result["distances"][0][i],
            }
        )
    return hits


def count() -> int:
    return get_collection().count()
