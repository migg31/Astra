"""Backfill historical CS-25 and CS-ACNS amendments into regulatory_node_versions.

Each entry is a consolidated document (not a delta) published by EASA.
They are ingested chronologically so that content_hash diffs are computed
correctly between consecutive versions.

Run with:
    python -m uv run python -m backend.harvest.backfill_history [--dry-run] [--source cs25|csacns|all]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.harvest.easa_fetcher import fetch_easa_xml
from backend.harvest.ingest import ingest

EASA_BASE = "https://www.easa.europa.eu"

# ── CS-25 — Large Aeroplanes ─────────────────────────────────────────────────
# Consolidated document per amendment (not deltas), chronological order.
CS25_VERSIONS: list[dict] = [
    {"version_label": "Initial Issue", "url": f"{EASA_BASE}/en/downloads/1516/en"},
    {"version_label": "Amendment 1",   "url": f"{EASA_BASE}/en/downloads/1561/en"},
    {"version_label": "Amendment 2",   "url": f"{EASA_BASE}/en/downloads/1563/en"},
    {"version_label": "Amendment 3",   "url": f"{EASA_BASE}/en/downloads/1566/en"},
    {"version_label": "Amendment 4",   "url": f"{EASA_BASE}/en/downloads/1569/en"},
    {"version_label": "Amendment 5",   "url": f"{EASA_BASE}/en/downloads/1572/en"},
    {"version_label": "Amendment 6",   "url": f"{EASA_BASE}/en/downloads/1575/en"},
    {"version_label": "Amendment 7",   "url": f"{EASA_BASE}/en/downloads/1578/en"},
    {"version_label": "Amendment 8",   "url": f"{EASA_BASE}/en/downloads/1581/en"},
    {"version_label": "Amendment 9",   "url": f"{EASA_BASE}/en/downloads/1584/en"},
    {"version_label": "Amendment 10",  "url": f"{EASA_BASE}/en/downloads/1587/en"},
    {"version_label": "Amendment 11",  "url": f"{EASA_BASE}/en/downloads/1590/en"},
    {"version_label": "Amendment 12",  "url": f"{EASA_BASE}/en/downloads/1714/en"},
    {"version_label": "Amendment 13",  "url": f"{EASA_BASE}/en/downloads/1982/en"},
    {"version_label": "Amendment 14",  "url": f"{EASA_BASE}/en/downloads/17500/en"},
    {"version_label": "Amendment 15",  "url": f"{EASA_BASE}/en/downloads/22035/en"},
    {"version_label": "Amendment 16",  "url": f"{EASA_BASE}/en/downloads/22035/en"},
    {"version_label": "Amendment 17",  "url": f"{EASA_BASE}/en/downloads/18864/en"},
    {"version_label": "Amendment 18",  "url": f"{EASA_BASE}/en/downloads/21117/en"},
    {"version_label": "Amendment 19",  "url": f"{EASA_BASE}/en/downloads/22504/en"},
    {"version_label": "Amendment 20",  "url": f"{EASA_BASE}/en/downloads/32288/en"},
    {"version_label": "Amendment 21",  "url": f"{EASA_BASE}/en/downloads/46017/en"},
    {"version_label": "Amendment 22",  "url": f"{EASA_BASE}/en/downloads/65402/en"},
    {"version_label": "Amendment 23",  "url": f"{EASA_BASE}/en/downloads/100573/en"},
    {"version_label": "Amendment 24",  "url": f"{EASA_BASE}/en/downloads/108354/en"},
    {"version_label": "Amendment 25",  "url": f"{EASA_BASE}/en/downloads/116279/en"},
    {"version_label": "Amendment 26",  "url": f"{EASA_BASE}/en/downloads/121128/en"},
    {"version_label": "Amendment 27",  "url": f"{EASA_BASE}/en/downloads/136622/en"},
    {"version_label": "Amendment 28",  "url": f"{EASA_BASE}/en/downloads/139073/en"},
]

CS25_SOURCE = {
    "name": "CS-25 — Large Aeroplanes",
    "external_id": "easa-cs25",
    "versions": CS25_VERSIONS,
}

# ── CS-ACNS — Airborne Communications, Navigation and Surveillance ───────────
CSACNS_VERSIONS: list[dict] = [
    {"version_label": "Initial Issue", "url": f"{EASA_BASE}/en/downloads/16743/en"},
    {"version_label": "Issue 2",       "url": f"{EASA_BASE}/en/downloads/96591/en"},
    {"version_label": "Issue 3",       "url": f"{EASA_BASE}/en/downloads/128205/en"},
    {"version_label": "Issue 4",       "url": f"{EASA_BASE}/en/downloads/136330/en"},
    {"version_label": "Issue 5",       "url": f"{EASA_BASE}/en/downloads/139873/en"},
]

CSACNS_SOURCE = {
    "name": "CS-ACNS — Airborne Communications, Navigation and Surveillance",
    "external_id": "easa-csacns",
    "versions": CSACNS_VERSIONS,
}

ALL_SOURCES = [CS25_SOURCE, CSACNS_SOURCE]


def _run_source(source: dict, data_dir: Path, dry_run: bool) -> None:
    name = source["name"]
    external_id = source["external_id"]
    versions = source["versions"]

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"  {len(versions)} versions to process")
    print(f"{'='*60}")

    seen_keys: set[tuple[str, str]] = set()

    for i, v in enumerate(versions, 1):
        label = v["version_label"]
        url = v["url"]
        print(f"\n[{i}/{len(versions)}] {label}")
        print(f"  URL: {url}")

        if dry_run:
            print("  [DRY RUN] skipping download and ingest")
            continue

        try:
            print("  Fetching...")
            fetched = fetch_easa_xml(data_dir, url, f"{external_id}-{label.lower().replace(' ', '-')}")
            size_kb = fetched.path.stat().st_size // 1024
            print(f"  Downloaded: {fetched.path.name} ({size_kb} KB)")
            print(f"  Hash: {fetched.content_hash[:12]}...")
        except Exception as e:
            print(f"  ERROR during fetch: {e}")
            print("  Skipping this version.")
            continue

        try:
            print("  Ingesting into PostgreSQL...")
            report = ingest(
                fetched.path,
                source_name=name,
                source_url=url,
                external_id=external_id,
                content_hash=fetched.content_hash,
                seen_keys=seen_keys,
            )
            print(f"  Nodes   : {report['nodes']} total")
            print(f"    added   : {report.get('nodes_added', 0)}")
            print(f"    modified: {report.get('nodes_modified', 0)}")
            print(f"    unchanged: {report.get('nodes_unchanged', 0)}")
            print(f"  Edges   : {report['edges_inserted']}")
        except Exception as e:
            print(f"  ERROR during ingest: {e}")
            print("  Skipping this version.")
            continue

        print(f"  Done — {label}")

    print(f"\n  Finished {name}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Backfill historical CS-25 and CS-ACNS amendments")
    parser.add_argument(
        "--source",
        choices=["cs25", "csacns", "all"],
        default="all",
        help="Which source to backfill (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List versions without downloading or ingesting",
    )
    parser.add_argument(
        "--from-version",
        type=str,
        default=None,
        help="Start from this version label (e.g. 'Amendment 15'), skip earlier ones",
    )
    args = parser.parse_args(argv)

    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    sources = ALL_SOURCES if args.source == "all" else (
        [CS25_SOURCE] if args.source == "cs25" else [CSACNS_SOURCE]
    )

    for source in sources:
        versions = source["versions"]
        if args.from_version:
            labels = [v["version_label"] for v in versions]
            if args.from_version in labels:
                start_idx = labels.index(args.from_version)
                source = {**source, "versions": versions[start_idx:]}
                print(f"Starting from: {args.from_version}")
            else:
                print(f"WARNING: '{args.from_version}' not found in {source['name']}, processing all.")

        _run_source(source, data_dir, dry_run=args.dry_run)

    print("\nBackfill complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
