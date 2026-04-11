"""API tests for /api/nodes.

These tests run against the live Postgres database (with the EASA Part 21
ingest already loaded) via an in-process httpx AsyncClient.
"""
import pytest
from httpx import ASGITransport, AsyncClient

from backend.api.main import app


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_list_nodes_by_type_and_q(client: AsyncClient):
    r = await client.get("/api/nodes", params={"node_type": "IR", "q": "21.A.91", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["reference_code"] == "21.A.91"
    assert body["items"][0]["node_type"] == "IR"


async def test_list_nodes_hierarchy_filter(client: AsyncClient):
    r = await client.get(
        "/api/nodes",
        params={"hierarchy_prefix": "Annex I / SECTION A", "limit": 500},
    )
    assert r.status_code == 200
    body = r.json()
    # Subparts B, D, E, G, J — at least 40 nodes expected
    assert body["total"] >= 40
    for item in body["items"]:
        assert item["hierarchy_path"].startswith("Annex I / SECTION A")


async def test_get_node_detail_and_neighbors(client: AsyncClient):
    listing = await client.get(
        "/api/nodes", params={"node_type": "IR", "q": "21.A.91", "limit": 1}
    )
    node_id = listing.json()["items"][0]["node_id"]

    detail = await client.get(f"/api/nodes/{node_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["reference_code"] == "21.A.91"
    assert "Classification of changes" in body["content_text"]
    # Unicode round-trip — typographic quotes must survive.
    assert "“minor”" in body["content_text"] or "\u201cminor\u201d" in body["content_text"]

    neighbors = await client.get(f"/api/nodes/{node_id}/neighbors")
    assert neighbors.status_code == 200
    nb = neighbors.json()
    relations_in = {e["relation"] for e in nb["incoming"]}
    # 21.A.91 has a GM and a GM appendix pointing at it, plus IR cross-refs.
    assert "GUIDANCE_FOR" in relations_in
    assert "REFERENCES" in relations_in


async def test_node_detail_fields(client: AsyncClient):
    """NodeDetail must expose content_html and optional metadata fields."""
    listing = await client.get(
        "/api/nodes", params={"node_type": "IR", "q": "21.A.91", "limit": 1}
    )
    node_id = listing.json()["items"][0]["node_id"]
    detail = await client.get(f"/api/nodes/{node_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert "content_html" in body
    assert body["content_html"] is not None  # 21.A.91 always has HTML
    # Optional fields must be present (may be null)
    assert "regulatory_source" in body
    assert "applicability_date" in body
    assert "entry_into_force_date" in body


async def test_get_node_404(client: AsyncClient):
    r = await client.get("/api/nodes/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


async def test_neighbors_relation_filter(client: AsyncClient):
    listing = await client.get(
        "/api/nodes", params={"node_type": "IR", "q": "21.A.91", "limit": 1}
    )
    node_id = listing.json()["items"][0]["node_id"]

    r = await client.get(
        f"/api/nodes/{node_id}/neighbors", params={"relation": "GUIDANCE_FOR"}
    )
    assert r.status_code == 200
    nb = r.json()
    assert all(e["relation"] == "GUIDANCE_FOR" for e in nb["incoming"])
    assert all(e["relation"] == "GUIDANCE_FOR" for e in nb["outgoing"])
