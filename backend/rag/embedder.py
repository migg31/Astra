"""Generate text embeddings via an OpenAI-compatible embeddings endpoint.

Provider is configured via settings (see backend/config.py):
  - Ollama local:  embed_base_url=http://localhost:11434/v1  embed_api_key=ollama
  - Nomic.ai:      embed_base_url=https://api-atlas.nomic.ai/v1  embed_api_key=<key>
  - Any other OpenAI-compatible provider works the same way.

The embedding model is separate from the chat model:
  - Chat:       settings.ollama_model      (mistral, llama-3.3-70b-versatile, ...)
  - Embeddings: settings.embed_model       (nomic-embed-text, nomic-embed-text-v1.5, ...)
"""
from __future__ import annotations

from openai import OpenAI

from backend.config import settings

# Keep legacy constants for any code that still imports them directly
OLLAMA_BASE_URL = settings.embed_base_url
EMBED_MODEL = settings.embed_model

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=settings.embed_base_url, api_key=settings.embed_api_key)
    return _client


def embed(text: str) -> list[float]:
    """Return the embedding vector for a single text."""
    response = _get_client().embeddings.create(model=settings.embed_model, input=text)
    return response.data[0].embedding


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a list of texts (one API call)."""
    response = _get_client().embeddings.create(model=settings.embed_model, input=texts)
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]
