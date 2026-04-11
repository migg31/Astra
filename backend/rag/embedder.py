"""Generate text embeddings via Ollama (nomic-embed-text model).

Ollama exposes an OpenAI-compatible /v1/embeddings endpoint, so we use the
openai client pointed at the local Ollama server.

The embedding model is separate from the chat model:
  - Chat:      mistral  (or any instruct model)
  - Embeddings: nomic-embed-text  (768-dim, fast, good quality)
"""
from __future__ import annotations

from openai import OpenAI

OLLAMA_BASE_URL = "http://localhost:11434/v1"
EMBED_MODEL = "nomic-embed-text"

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    return _client


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single text."""
    response = _get_client().embeddings.create(model=EMBED_MODEL, input=text)
    return response.data[0].embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a list of texts (one API call)."""
    response = _get_client().embeddings.create(model=EMBED_MODEL, input=texts)
    # Preserve original order (OpenAI API returns them in order).
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
