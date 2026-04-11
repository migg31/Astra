"""Orchestrate EASA Part 21 ingestion: fetch → parse → persist.

Run with:

    python -m uv run python -m backend.harvest.ingest
    python -m uv run python -m backend.harvest.ingest --offline path/to/part21.xml
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from backend.config import settings
from backend.harvest.easa_fetcher import PART21_XML_ZIP_URL, fetch_part21_xml
from backend.harvest.easa_parser import parse_easa_xml
from backend.harvest.models import ParseResult

SOURCE_NAME = "EASA Easy Access Rules — Part 21"
SOURCE_FORMAT = "MIXED"        # the file is XML but packaged inside a zip/docx
SOURCE_FREQUENCY = "monthly"


def upsert_source(cur) -> str:
    cur.execute(
        """
        INSERT INTO harvest_sources (name, base_url, format, frequency, last_sync_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (name) DO UPDATE
            SET base_url     = EXCLUDED.base_url,
                format       = EXCLUDED.format,
                frequency    = EXCLUDED.frequency,
                last_sync_at = NOW()
        RETURNING source_id
        """,
        (SOURCE_NAME, PART21_XML_ZIP_URL, SOURCE_FORMAT, SOURCE_FREQUENCY),
    )
    return cur.fetchone()[0]


def upsert_document(
    cur,
    source_id: str,
    external_id: str,
    title: str,
    url: str,
    content_hash: str,
    raw_path: str,
) -> str:
    cur.execute(
        """
        INSERT INTO harvest_documents
            (source_id, external_id, title, url, content_hash, raw_path)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
            SET title        = EXCLUDED.title,
                url          = EXCLUDED.url,
                content_hash = EXCLUDED.content_hash,
                raw_path     = EXCLUDED.raw_path,
                fetched_at   = NOW()
        RETURNING doc_id
        """,
        (source_id, external_id, title, url, content_hash, raw_path),
    )
    return cur.fetchone()[0]


def upsert_nodes(cur, doc_id: str, result: ParseResult) -> dict[tuple[str, str], str]:
    """Upsert all parsed nodes and return a mapping (node_type, reference_code) → node_id."""
    rows = [
        (
            n.node_type,
            n.reference_code,
            n.title,
            n.content_text,
            n.content_html,
            n.content_hash,
            n.hierarchy_path,
            doc_id,
        )
        for n in result.nodes
    ]
    execute_values(
        cur,
        """
        INSERT INTO regulatory_nodes
            (node_type, reference_code, title, content_text, content_html, content_hash,
             hierarchy_path, source_doc_id)
        VALUES %s
        ON CONFLICT (node_type, reference_code) DO UPDATE
            SET title         = EXCLUDED.title,
                content_text  = EXCLUDED.content_text,
                content_html  = EXCLUDED.content_html,
                content_hash  = EXCLUDED.content_hash,
                hierarchy_path= EXCLUDED.hierarchy_path,
                source_doc_id = EXCLUDED.source_doc_id,
                updated_at    = NOW()
        """,
        rows,
        template="(%s::node_type, %s, %s, %s, %s, %s, %s, %s)",
    )

    cur.execute(
        "SELECT node_type::text, reference_code, node_id FROM regulatory_nodes"
    )
    return {(r[0], r[1]): r[2] for r in cur.fetchall()}


def upsert_edges(cur, node_map: dict[tuple[str, str], str], result: ParseResult) -> int:
    rows = []
    for edge in result.edges:
        # Look up source node: try each type prefix until we find one.
        source_id = None
        for candidate_type in ("IR", "AMC", "GM", "CS"):
            nid = node_map.get((candidate_type, edge.source_ref))
            if nid:
                source_id = nid
                break
        target_id = node_map.get(("IR", edge.target_ref))
        if not source_id or not target_id or source_id == target_id:
            continue
        rows.append((source_id, target_id, edge.relation, edge.confidence, edge.notes))

    if not rows:
        return 0

    execute_values(
        cur,
        """
        INSERT INTO regulatory_edges
            (source_node_id, target_node_id, relation, confidence, notes)
        VALUES %s
        ON CONFLICT (source_node_id, target_node_id, relation) DO NOTHING
        """,
        rows,
        template="(%s, %s, %s::edge_type, %s, %s)",
    )
    return len(rows)


def ingest(xml_path: Path, *, source_url: str, content_hash: str) -> dict:
    result = parse_easa_xml(xml_path)

    external_id = "easa-part21-748-2012"
    title = result.source_document_title or "EASA Part 21"

    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            source_id = upsert_source(cur)
            doc_id = upsert_document(
                cur,
                source_id=source_id,
                external_id=external_id,
                title=title,
                url=source_url,
                content_hash=content_hash,
                raw_path=str(xml_path.resolve()),
            )
            node_map = upsert_nodes(cur, doc_id, result)
            edges_inserted = upsert_edges(cur, node_map, result)
        conn.commit()

    return {
        "source_id": source_id,
        "doc_id": doc_id,
        "nodes": len(result.nodes),
        "edges_attempted": len(result.edges),
        "edges_inserted": edges_inserted,
        "pub_time": result.source_pub_time,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest EASA Part 21 into Postgres")
    parser.add_argument(
        "--offline",
        type=Path,
        help="Path to an already-downloaded pkg:package XML; skips the network fetch",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory where raw downloads are cached (default: ./data)",
    )
    args = parser.parse_args(argv)

    if args.offline:
        xml_path = args.offline.resolve()
        content_hash = _quick_hash(xml_path)
        source_url = PART21_XML_ZIP_URL
        print(f"[offline] using {xml_path}")
    else:
        print("[fetch] downloading EASA Part 21 XML ...")
        fetched = fetch_part21_xml(args.data_dir)
        xml_path = fetched.path
        content_hash = fetched.content_hash
        source_url = fetched.url
        print(f"[fetch] saved to {xml_path} ({content_hash[:8]})")

    print("[parse+persist] running ...")
    report = ingest(xml_path, source_url=source_url, content_hash=content_hash)
    print(f"[done] {report}")
    return 0


def _quick_hash(path: Path) -> str:
    import hashlib

    h = hashlib.md5()  # noqa: S324
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


if __name__ == "__main__":
    sys.exit(main())
