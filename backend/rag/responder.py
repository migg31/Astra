"""Generate a sourced answer from retrieved regulatory context.

Uses Ollama (mistral) via the OpenAI-compatible chat endpoint.
Anti-hallucination constraints are enforced at the prompt level:
  - The model may ONLY use information from the provided excerpts.
  - Every claim must cite its source by reference_code.
  - The model must add a disclaimer that this is not regulatory advice.
  - If the context is insufficient, the model must say so explicitly.
"""
from __future__ import annotations

import logging
import re

from fastapi import HTTPException
from openai import OpenAI, APIConnectionError

from backend.config import settings

logger = logging.getLogger(__name__)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(base_url=settings.ollama_base_url, api_key=settings.ollama_api_key)
    return _client

SYSTEM_PROMPT = """You are Astra, a regulatory knowledge assistant specialised in EASA aviation regulations.

STRICT RULES — you must follow them without exception:
1. Answer ONLY using the regulatory excerpts provided. Quote or paraphrase them directly.
2. Do NOT use any external knowledge, even if you believe it to be correct.
3. Cite every factual claim with its source in brackets, e.g. [21.A.91] or [AMC 21.A.97].
4. Structure your answer clearly: start with a direct answer to the question, then elaborate with details from the excerpts.
5. Cover ALL relevant excerpts provided — if multiple articles address different aspects of the question, mention each one. Do not focus only on the most prominent article.
6. If the excerpts contain the answer, give it fully — do not say "insufficient information" if the answer is present.
7. If the excerpts truly do not contain the answer, say: "The provided regulatory excerpts do not contain enough information to answer this question."
8. If the question asks about a specific document (e.g. "CS-25", "Part 21") but the excerpts are from a different document, explicitly note this mismatch before answering.
9. Never make a compliance determination or regulatory decision on behalf of the user.
10. End every response with this disclaimer on its own line:
   ⚠️ This response is provided for informational purposes only and does not constitute regulatory or legal advice.

Response language: English."""


_RERANK_SCORE_RE = re.compile(r"\b([0-9]|10)\b")

_EXPAND_SYSTEM = (
    "You are an EASA regulatory reference assistant. "
    "Given a question about aviation regulations, output ONLY a comma-separated list of "
    "specific EASA article codes that are most likely to answer it. "
    "Use CS-25 article numbers (digits only, like 25.1323) or typed codes (like AMC 25.1323). "
    "Output at most 8 codes. If the question already contains article codes, output them as-is. "
    "Domain hints: air data / pitot-static / airspeed / altitude → 25.1323, 25.1325, 25.1326, 25.1327, 25.1333; "
    "instrument systems independence / failure → 25.1333; flight data recorder → 25.1459; "
    "airworthiness limits → 25.571; fuel systems → 25.951-25.979. "
    "Output NOTHING else — no explanation, no punctuation other than commas."
)

_CODE_RE = re.compile(r"\b\d{2,3}\.\d+[A-Z]?\b")


def expand_query(question: str) -> list[str]:
    """Use the LLM to extract probable article codes from a vague question.

    Returns a list of bare article codes (e.g. ['25.1323', '25.1325']).
    Falls back to empty list on any failure.
    """
    client = _get_client()
    try:
        resp = client.chat.completions.create(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _EXPAND_SYSTEM},
                {"role": "user",   "content": question},
            ],
            temperature=0.0,
            max_tokens=100,
        )
        raw = (resp.choices[0].message.content or "").strip()
        codes = [c.strip() for c in raw.split(",") if c.strip()]
        return [c for c in codes if _CODE_RE.search(c)][:8]
    except Exception:
        logger.debug("expand_query: LLM call failed")
        return []

_RERANK_SYSTEM = (
    "You are a relevance scoring assistant for an EASA regulatory knowledge base. "
    "You will receive a question and a numbered list of regulatory excerpts. "
    "Output ONLY a JSON object mapping each excerpt number (as string key) to an integer score 0-10. "
    "10 = directly and fully answers the question. 0 = completely irrelevant. "
    'Example output for 3 excerpts: {"1": 8, "2": 3, "3": 6}. Output NOTHING else.'
)


def rerank(question: str, hits: list[dict], top_n: int = 4, min_score: int = 6) -> list[dict]:
    """Batch LLM reranker: score all hits in one call, return top_n above min_score.

    Falls back to original order if the LLM call fails or returns unparseable output.
    """
    import json as _json
    if len(hits) <= top_n:
        return hits
    client = _get_client()
    # Build numbered excerpt list
    lines = []
    for i, hit in enumerate(hits, 1):
        ref = hit["metadata"].get("reference_code", "")
        snippet = hit["document"][:500]
        lines.append(f"[{i}] {ref}\n{snippet}")
    prompt = f"QUESTION: {question}\n\nEXCERPTS:\n" + "\n---\n".join(lines)
    try:
        resp = client.chat.completions.create(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": _RERANK_SYSTEM},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.0,
            max_tokens=120,
        )
        raw = (resp.choices[0].message.content or "").strip()
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL).strip()
        scores_map: dict[str, int] = _json.loads(clean)
        scored = [(int(scores_map.get(str(i), 5)), hit) for i, hit in enumerate(hits, 1)]
    except Exception:
        logger.debug("rerank: batch LLM call failed, falling back to original order")
        scored = [(5, hit) for hit in hits]
    scored.sort(key=lambda x: x[0], reverse=True)
    # Apply min_score threshold but always keep at least 1 result
    filtered = [(s, h) for s, h in scored if s >= min_score]
    if not filtered:
        filtered = scored[:1]
    return [h for _, h in filtered[:top_n]]


def _build_context(hits: list[dict]) -> str:
    parts = []
    for h in hits:
        meta = h["metadata"]
        ref = meta["reference_code"]
        title = meta.get("title", "")
        header = f"[{ref}]" + (f" — {title}" if title else "")
        parts.append(f"{header}\n{h['document'][:2000]}")
    return "\n\n---\n\n".join(parts)


def _extract_cited_ids(answer_text: str, hits: list[dict]) -> list[str]:
    """Find which node ids are cited in the answer by matching their reference_code.

    Returns ordered list of node_ids deduped by base ref code (strips suffixes like (d),(e)).
    """
    cited: list[str] = []
    seen_refs: set[str] = set()
    seen_ids: set[str] = set()
    for h in hits:
        meta = h["metadata"]
        ref = meta["reference_code"]
        node_id = meta.get("node_id") or meta.get("parent_node_id") or h["id"]
        # Skip sub-variants like AMC 25.1323(d) — they are never directly cited
        if re.search(r"\([a-z0-9]+\)\s*$", ref, re.IGNORECASE):
            continue
        # Deduplicate by reference code
        if ref in seen_refs or node_id in seen_ids:
            continue
        pattern = re.escape(ref)
        if re.search(pattern, answer_text, re.IGNORECASE):
            cited.append(node_id)
            seen_refs.add(ref)
            seen_ids.add(node_id)
    return cited


def answer(question: str, hits: list[dict]) -> tuple[str, list[str]]:
    """Call LLM and return (answer_text, cited_node_ids)."""
    context = _build_context(hits)
    user_message = (
        f"REGULATORY EXCERPTS:\n\n{context}\n\n"
        f"QUESTION: {question}"
    )
    client = _get_client()
    try:
        response = client.chat.completions.create(
            model=settings.ollama_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": user_message},
            ],
            temperature=0.1,
            max_tokens=800,
        )
    except APIConnectionError as exc:
        raise HTTPException(
            status_code=503,
            detail="AI service unavailable — make sure Ollama is running.",
        ) from exc
    answer_text = (response.choices[0].message.content or "").strip()
    cited_node_ids = _extract_cited_ids(answer_text, hits)
    return answer_text, cited_node_ids
