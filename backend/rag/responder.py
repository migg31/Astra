"""Generate a sourced answer from retrieved regulatory context.

Uses Ollama (mistral) via the OpenAI-compatible chat endpoint.
Anti-hallucination constraints are enforced at the prompt level:
  - The model may ONLY use information from the provided excerpts.
  - Every claim must cite its source by reference_code.
  - The model must add a disclaimer that this is not regulatory advice.
  - If the context is insufficient, the model must say so explicitly.
"""
from __future__ import annotations

from openai import OpenAI

OLLAMA_BASE_URL = "http://localhost:11434/v1"
CHAT_MODEL = "mistral"

_client: OpenAI | None = None

SYSTEM_PROMPT = """You are Astra, a regulatory knowledge assistant specialised in EASA Part 21 aviation certification.

STRICT RULES — you must follow them without exception:
1. Answer ONLY using the regulatory excerpts provided. Quote or paraphrase them directly.
2. Do NOT use any external knowledge, even if you believe it to be correct.
3. Cite every factual claim with its source in brackets, e.g. [21.A.91] or [AMC 21.A.97].
4. Structure your answer clearly: start with a direct answer to the question, then elaborate with details from the excerpts.
5. If the excerpts contain the answer, give it fully — do not say "insufficient information" if the answer is present.
6. If the excerpts truly do not contain the answer, say: "The provided regulatory excerpts do not contain enough information to answer this question."
7. Never make a compliance determination or regulatory decision on behalf of the user.
8. End every response with this disclaimer on its own line:
   ⚠️ This response is provided for informational purposes only and does not constitute regulatory or legal advice.

Response language: English."""


def _build_context(hits: list[dict]) -> str:
    parts = []
    for h in hits:
        meta = h["metadata"]
        ref = meta["reference_code"]
        title = meta.get("title", "")
        header = f"[{ref}]" + (f" — {title}" if title else "")
        parts.append(f"{header}\n{h['document'][:2000]}")
    return "\n\n---\n\n".join(parts)


def answer(question: str, hits: list[dict]) -> str:
    """Call Ollama/mistral and return the generated answer string."""
    context = _build_context(hits)
    user_message = (
        f"REGULATORY EXCERPTS:\n\n{context}\n\n"
        f"QUESTION: {question}"
    )
    client = _get_client()
    response = client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ],
        temperature=0.1,   # low temperature for factual/regulatory answers
        max_tokens=1024,
    )
    return response.choices[0].message.content or ""


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")
    return _client
