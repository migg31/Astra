"""Orchestrate EASA Part 21 ingestion: fetch → parse → persist.

Run with:

    python -m uv run python -m backend.harvest.ingest
    python -m uv run python -m backend.harvest.ingest --offline path/to/part21.xml
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

from backend.config import settings
from backend.harvest.easa_fetcher import fetch_easa_document, fetch_part21_xml, PART21_XML_ZIP_URL
from backend.harvest.easa_parser import parse_easa_xml
from backend.harvest.easa_html_parser import parse_easa_html
from backend.harvest.pdf_cs_parser import parse_cs_pdf
from backend.harvest.pdf_smart_parser import parse_smart_pdf
from backend.harvest.pdf_narrative_parser import parse_narrative_pdf
from backend.harvest.models import ParseResult


def _word_diff(old: str, new: str) -> list[dict]:
    """Compute a word-level diff between two texts.
    Returns a list of {op, text} dicts: op = 'equal' | 'insert' | 'delete'.
    Truncated to 500 ops to keep JSONB size reasonable.
    """
    old_words = old.split()
    new_words = new.split()
    matcher = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
    ops: list[dict] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append({"op": "equal", "text": " ".join(old_words[i1:i2])})
        elif tag == "insert":
            ops.append({"op": "insert", "text": " ".join(new_words[j1:j2])})
        elif tag == "delete":
            ops.append({"op": "delete", "text": " ".join(old_words[i1:i2])})
        elif tag == "replace":
            ops.append({"op": "delete", "text": " ".join(old_words[i1:i2])})
            ops.append({"op": "insert", "text": " ".join(new_words[j1:j2])})
    return ops[:500]

def _load_sources_from_db() -> dict[str, dict]:
    """Load all enabled source_files from DB as {external_id: cfg_dict}.
    cfg_dict keys: name, external_id, urls (dict), use_smart_parser (bool).
    """
    conn = psycopg2.connect(settings.database_url_sync)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT external_id, name, urls FROM source_files WHERE enabled = TRUE ORDER BY name"
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    sources: dict[str, dict] = {}
    for external_id, name, urls_json in rows:
        urls = urls_json or {}
        use_smart_parser = bool(urls.pop("use_smart_parser", True))
        use_narrative_parser = bool(urls.pop("use_narrative_parser", False))
        sources[external_id] = {
            "name": name,
            "external_id": external_id,
            "urls": urls,
            "use_smart_parser": use_smart_parser,
            "use_narrative_parser": use_narrative_parser,
        }
    return sources


SOURCE_FORMAT = "MIXED"
SOURCE_FREQUENCY = "monthly"


def upsert_source(cur, name: str, url: str, external_id: str | None = None) -> str:
    if external_id:
        # Prefer upsert by external_id to avoid duplicates on rename
        cur.execute(
            """
            INSERT INTO source_files (external_id, name, base_url, format, frequency, last_sync_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON CONFLICT (external_id) DO UPDATE
                SET name         = EXCLUDED.name,
                    base_url     = EXCLUDED.base_url,
                    format       = EXCLUDED.format,
                    frequency    = EXCLUDED.frequency,
                    last_sync_at = NOW()
            RETURNING source_id
            """,
            (external_id, name, url, SOURCE_FORMAT, SOURCE_FREQUENCY),
        )
    else:
        cur.execute(
            """
            INSERT INTO source_files (name, base_url, format, frequency, last_sync_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (name) DO UPDATE
                SET base_url     = EXCLUDED.base_url,
                    format       = EXCLUDED.format,
                    frequency    = EXCLUDED.frequency,
                    last_sync_at = NOW()
            RETURNING source_id
            """,
            (name, url, SOURCE_FORMAT, SOURCE_FREQUENCY),
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
    version_label: str | None = None,
    pub_date=None,
    amended_by: str | None = None,
    is_latest: bool = False,
) -> str:
    cur.execute(
        """
        INSERT INTO harvest_documents
            (source_id, external_id, title, url, content_hash, raw_path,
             version_label, pub_date, amended_by, is_latest)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id, external_id) DO UPDATE
            SET title         = EXCLUDED.title,
                url           = EXCLUDED.url,
                content_hash  = EXCLUDED.content_hash,
                raw_path      = EXCLUDED.raw_path,
                version_label = EXCLUDED.version_label,
                pub_date      = EXCLUDED.pub_date,
                amended_by    = EXCLUDED.amended_by,
                is_latest     = EXCLUDED.is_latest,
                fetched_at    = NOW()
        RETURNING doc_id
        """,
        (source_id, external_id, title, url, content_hash, raw_path,
         version_label, pub_date, amended_by, is_latest),
    )
    return cur.fetchone()[0]


def upsert_nodes(
    cur,
    doc_id: str,
    result: ParseResult,
    version_label: str,
    seen_keys: set[tuple[str, str]] | None = None,
    is_latest: bool = False,
) -> dict[tuple[str, str], str]:
    """Upsert all parsed nodes, record version snapshots, return (node_type, reference_code) → node_id.

    is_latest: if True, fully upsert into regulatory_nodes (update content + hierarchy_path).
               if False (historical backfill), only write to regulatory_node_versions — never
               overwrite the canonical state in regulatory_nodes.
    seen_keys: optional shared set across multiple sources in the same run.
    """

    # ── 1. Fetch current hashes + content for changed-node detection ──────
    cur.execute(
        "SELECT node_type::text, reference_code, node_id, content_hash, content_text "
        "FROM regulatory_nodes"
    )
    existing: dict[tuple[str, str], tuple[str, str, str]] = {
        (r[0], r[1]): (str(r[2]), r[3], r[4]) for r in cur.fetchall()
    }

    # ── 2. Upsert nodes (only when is_latest) ────────────────────────────
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
            n.regulatory_source,
            n.applicability_date,
            n.entry_into_force_date,
        )
        for n in result.nodes
    ]
    if is_latest:
        execute_values(
            cur,
            """
            INSERT INTO regulatory_nodes
                (node_type, reference_code, title, content_text, content_html, content_hash,
                 hierarchy_path, source_doc_id, regulatory_source,
                 applicability_date, entry_into_force_date)
            VALUES %s
            ON CONFLICT (node_type, reference_code) DO UPDATE
                SET title                 = EXCLUDED.title,
                    content_text          = EXCLUDED.content_text,
                    content_html          = EXCLUDED.content_html,
                    content_hash          = EXCLUDED.content_hash,
                    hierarchy_path        = EXCLUDED.hierarchy_path,
                    source_doc_id         = EXCLUDED.source_doc_id,
                    regulatory_source     = EXCLUDED.regulatory_source,
                    applicability_date    = EXCLUDED.applicability_date,
                    entry_into_force_date = EXCLUDED.entry_into_force_date,
                    updated_at            = NOW()
            """,
            rows,
            template="(%s::node_type, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
        )

    # ── 2b. Delete stale nodes (present in DB for this doc but absent from current batch) ──────
    nodes_removed = 0
    if is_latest and result.nodes:
        current_keys = {(n.node_type, n.reference_code) for n in result.nodes}
        cur.execute(
            "SELECT node_type::text, reference_code, node_id FROM regulatory_nodes WHERE source_doc_id = %s",
            (doc_id,),
        )
        stale_rows = [(r[0], r[1], str(r[2])) for r in cur.fetchall() if (r[0], r[1]) not in current_keys]
        if stale_rows:
            stale_ids = [r[2] for r in stale_rows]
            cur.execute("DELETE FROM regulatory_nodes WHERE node_id = ANY(%s::uuid[])", (stale_ids,))
            nodes_removed = len(stale_rows)

    # ── 3. Reload node_ids ────────────────────────────────────────────────
    cur.execute(
        "SELECT node_type::text, reference_code, node_id FROM regulatory_nodes"
    )
    node_map = {(r[0], r[1]): str(r[2]) for r in cur.fetchall()}

    # ── 4. Build version snapshots ────────────────────────────────────────
    version_rows: list[tuple] = []
    counters = {"added": 0, "modified": 0, "unchanged": 0, "deleted": nodes_removed}

    for n in result.nodes:
        key = (n.node_type, n.reference_code)
        node_id = node_map.get(key)
        if not node_id:
            continue

        prev = existing.get(key)
        if prev is None:
            change_type = "added"
            diff_prev = None
        elif prev[1] != n.content_hash:
            change_type = "modified"
            diff_prev = json.dumps(_word_diff(prev[2] or "", n.content_text or ""))
        else:
            change_type = "unchanged"
            diff_prev = None

        counters[change_type] = counters.get(change_type, 0) + 1

        # Only persist added/modified snapshots (skip unchanged to save space)
        if change_type in ("added", "modified"):
            if seen_keys is not None and key in seen_keys:
                counters[change_type] -= 1
                counters["unchanged"] = counters.get("unchanged", 0) + 1
                continue
            version_rows.append((
                node_id,
                version_label,
                n.content_text,
                n.content_html,
                n.content_hash,
                change_type,
                diff_prev,
            ))
        if seen_keys is not None:
            seen_keys.add(key)

    if version_rows:
        execute_values(
            cur,
            """
            INSERT INTO regulatory_node_versions
                (node_id, version_label, content_text, content_html,
                 content_hash, change_type, diff_prev)
            VALUES %s
            """,
            version_rows,
            template="(%s, %s, %s, %s, %s, %s, %s::jsonb)",
        )

    return node_map, counters


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
        target_id = node_map.get(("IR", edge.target_ref)) or node_map.get(("CS", edge.target_ref))
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
    return cur.rowcount  # actual rows inserted (excludes DO NOTHING conflicts)


def ingest(file_path: Path, *, source_name: str, source_url: str, external_id: str, content_hash: str, doc_format: str = "xml", use_smart_parser: bool = True, use_narrative_parser: bool = False, seen_keys: set[tuple[str, str]] | None = None, is_latest: bool = False, progress_callback=None) -> dict:
    if doc_format == "pdf" and use_narrative_parser:
        result = parse_narrative_pdf(file_path, regulatory_source=source_name)
    elif doc_format == "pdf" and not use_smart_parser:
        result = parse_cs_pdf(file_path, regulatory_source=source_name)
    elif doc_format == "pdf":
        result = parse_smart_pdf(file_path, regulatory_source=source_name, progress_callback=progress_callback)
    elif doc_format == "html":
        result = parse_easa_html(file_path, regulatory_source=source_name)
    else:
        # Default to XML (includes DOCX)
        result = parse_easa_xml(file_path)

    title = result.source_document_title or source_name
    version_label = result.source_version or "Unknown"

    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            source_id = upsert_source(cur, source_name, source_url, external_id=external_id)
            doc_id = upsert_document(
                cur,
                source_id=source_id,
                external_id=external_id,
                title=title,
                url=source_url,
                content_hash=content_hash,
                raw_path=str(file_path.resolve()),
                version_label=version_label,
                pub_date=result.source_pub_time.date() if result.source_pub_time else None,
                amended_by=result.source_version,
                is_latest=is_latest,
            )
            node_map, counters = upsert_nodes(cur, doc_id, result, version_label, seen_keys=seen_keys, is_latest=is_latest)
            edges_inserted = upsert_edges(cur, node_map, result)

            # ── Record harvest run summary ────────────────────────────────
            cur.execute(
                """
                INSERT INTO document_harvest_runs
                    (doc_id, version_label, nodes_added, nodes_modified,
                     nodes_deleted, nodes_unchanged, nodes_total)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    doc_id,
                    version_label,
                    counters.get("added", 0),
                    counters.get("modified", 0),
                    counters.get("deleted", 0),
                    counters.get("unchanged", 0),
                    len(result.nodes),
                ),
            )
        conn.commit()

        # ── Auto-fill doc_title_pattern for any doc_sources linked to this source ──
        # Runs only when pattern is NULL so it never overrides a manual value.
        if title:
            with psycopg2.connect(settings.database_url_sync) as conn2:
                with conn2.cursor() as cur2:
                    cur2.execute(
                        """
                        UPDATE regulations
                        SET doc_title_pattern = %s
                        WHERE harvest_key = %s
                          AND doc_title_pattern IS NULL
                        """,
                        (f"%{title[:60]}%", external_id),
                    )
                conn2.commit()

    return {
        "source_name": source_name,
        "source_id": source_id,
        "doc_id": doc_id,
        "nodes": len(result.nodes),
        "nodes_added": counters.get("added", 0),
        "nodes_modified": counters.get("modified", 0),
        "nodes_deleted": counters.get("deleted", 0),
        "nodes_unchanged": counters.get("unchanged", 0),
        "edges_attempted": len(result.edges),
        "edges_inserted": edges_inserted,
        "edges_skipped": len(result.edges) - edges_inserted,
        "pub_time": result.source_pub_time,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest EASA Rules into Postgres")
    parser.add_argument(
        "--source",
        help="external_id of the source to ingest (as stored in source_files)",
        default="easa-part21",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="List all enabled sources from DB and exit",
    )
    parser.add_argument(
        "--offline",
        type=Path,
        help="Path to an already-downloaded document (XML, DOCX, PDF, HTML); skips the network fetch",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Directory where raw downloads are cached (default: ./data)",
    )
    args = parser.parse_args(argv)

    sources = _load_sources_from_db()

    if args.list_sources:
        for eid, cfg in sorted(sources.items()):
            print(f"  {eid:30s} {cfg['name']}")
        return 0

    if args.source not in sources:
        print(f"[error] unknown source '{args.source}'. Use --list-sources to see available sources.")
        return 1

    source_cfg = sources[args.source]

    if args.offline:
        file_path = args.offline.resolve()
        content_hash = _quick_hash(file_path)
        source_url = source_cfg["urls"].get("xml") or source_cfg["urls"].get("html") or source_cfg["urls"].get("pdf")

        ext = file_path.suffix.lower()
        if ext == ".pdf":
            doc_format = "pdf"
        elif ext in (".html", ".htm"):
            doc_format = "html"
        else:
            doc_format = "xml"

        print(f"[offline] using {file_path} (format: {doc_format})")
    else:
        print(f"[fetch] downloading {source_cfg['name']} ...")
        fetched = fetch_easa_document(args.data_dir, source_cfg["urls"], source_cfg["external_id"])
        file_path = fetched.path
        content_hash = fetched.content_hash
        source_url = fetched.url
        doc_format = fetched.format
        print(f"[fetch] saved to {file_path} ({content_hash[:8]}, format: {doc_format})")

    print("[parse+persist] running ...")
    report = ingest(
        file_path,
        source_name=source_cfg["name"],
        source_url=source_url,
        external_id=source_cfg["external_id"],
        content_hash=content_hash,
        doc_format=doc_format,
        use_smart_parser=source_cfg.get("use_smart_parser", True),
        is_latest=True,
    )
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
