"""RAG quality regression tests.

Run with:
    python -m pytest tests/test_rag_quality.py -v

Requires backend running on localhost:8000.
Each test posts a question and checks that expected article codes appear
in cited_nodes AND that the answer text is non-trivial.
"""
from __future__ import annotations

import re
import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 60  # Groq + reranker can take a few seconds


def ask(question: str, source_filter: str | None = None) -> dict:
    payload: dict = {"question": question}
    if source_filter:
        payload["source_filter"] = source_filter
    r = httpx.post(f"{BASE_URL}/api/ask", json=payload, timeout=TIMEOUT)
    r.raise_for_status()
    return r.json()


def cited_refs(response: dict) -> set[str]:
    """Return set of reference_codes from cited_nodes."""
    return {cn["reference_code"] for cn in response.get("cited_nodes", [])}


def source_refs(response: dict) -> set[str]:
    """Return set of reference_codes from sources."""
    return {s["reference_code"] for s in response.get("sources", [])}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestAirDataCS25:
    """Air data handling in CS 25 — expected articles: 1323, 1325, 1326, 1333."""

    QUESTION = "How air data is handled by CS 25?"
    EXPECTED_CITED = {"CS 25.1323", "CS 25.1325"}
    EXPECTED_SOURCES_FAMILIES = {"25.1323", "25.1325", "25.1326", "25.1333"}
    EXPECTED_KEYWORDS = ["airspeed", "static pressure", "calibrat"]

    @pytest.fixture(scope="class")
    def response(self):
        return ask(self.QUESTION)

    def test_cited_core_articles(self, response):
        """Must cite 25.1323 and 25.1325 in answer."""
        refs = cited_refs(response)
        missing = self.EXPECTED_CITED - refs
        assert not missing, f"Missing cited articles: {missing}. Got: {refs}"

    def test_sources_coverage(self, response):
        """Sources must cover all 4 key air data article families (CS or AMC variant)."""
        refs = source_refs(response)
        # Extract numeric part from each ref, e.g. 'CS 25.1333' -> '25.1333', 'AMC 25.1333(b)' -> '25.1333'
        present_families = {re.search(r'\d{2,3}\.\d+', r).group() for r in refs if re.search(r'\d{2,3}\.\d+', r)}
        missing = self.EXPECTED_SOURCES_FAMILIES - present_families
        assert not missing, f"Missing article families: {missing}. Present: {present_families}"

    def test_answer_non_trivial(self, response):
        """Answer must be at least 200 chars."""
        answer = response.get("answer", "")
        assert len(answer) >= 200, f"Answer too short ({len(answer)} chars)"

    def test_answer_keywords(self, response):
        """Answer must mention key air data concepts."""
        answer = response.get("answer", "").lower()
        missing = [kw for kw in self.EXPECTED_KEYWORDS if kw.lower() not in answer]
        assert not missing, f"Answer missing keywords: {missing}"

    def test_no_uuid_in_cited(self, response):
        """No raw UUIDs should appear in cited_nodes reference_codes."""
        uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-", re.IGNORECASE)
        bad = [cn["reference_code"] for cn in response.get("cited_nodes", [])
               if uuid_re.match(cn["reference_code"])]
        assert not bad, f"UUID reference_codes in cited_nodes: {bad}"

    def test_no_duplicate_source_family(self, response):
        """Source list must not contain multiple AMC variants of same article."""
        base_refs = [
            re.sub(r"\s*\([^)]*\)\s*$", "", s["reference_code"]).strip()
            for s in response.get("sources", [])
        ]
        seen: set[str] = set()
        dupes = []
        for r in base_refs:
            if r in seen:
                dupes.append(r)
            seen.add(r)
        assert not dupes, f"Duplicate base refs in sources: {dupes}"


class TestExpandQuery:
    """expand_query must suggest the right articles for vague questions."""

    def test_air_data_expansion(self):
        from backend.rag.responder import expand_query
        codes = expand_query("How air data is handled by CS 25?")
        code_nums = {c.split(".")[-1] for c in codes}
        assert "1323" in code_nums, f"25.1323 missing from expand_query: {codes}"
        assert "1325" in code_nums, f"25.1325 missing from expand_query: {codes}"
        assert "1333" in code_nums, f"25.1333 missing from expand_query: {codes}"

    def test_instrument_failure_expansion(self):
        from backend.rag.responder import expand_query
        codes = expand_query("What are the requirements for instrument failure in CS 25?")
        code_nums = {c.split(".")[-1] for c in codes}
        assert "1333" in code_nums, f"25.1333 missing: {codes}"


class TestSourceDedup:
    """Sources must deduplicate AMC variant families."""

    QUESTION = "What are the requirements for airspeed indication in CS 25?"

    @pytest.fixture(scope="class")
    def response(self):
        return ask(self.QUESTION)

    def test_amc_25_1323_single_entry(self, response):
        """AMC 25.1323 must appear at most once in sources."""
        amc_sources = [
            s for s in response.get("sources", [])
            if "AMC 25.1323" in s["reference_code"] or "AMC 25.1323" == re.sub(r"\s*\([^)]*\)\s*$", "", s["reference_code"]).strip()
        ]
        assert len(amc_sources) <= 1, f"AMC 25.1323 appears {len(amc_sources)} times: {[s['reference_code'] for s in amc_sources]}"
