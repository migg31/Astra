"""Full reset: drop + recreate all SQL tables, wipe ChromaDB collection.

Run with:
    python -m uv run python -m backend.database.reset_all

WARNING: destroys ALL data irreversibly.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import psycopg2
from backend.config import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
CHROMA_PATH = Path(__file__).resolve().parents[2] / "data" / "chroma"

# Ordered list of migration files to replay after reset
MIGRATION_FILES = [
    "001_initial_schema.sql",
    "002_add_content_html.sql",
    "003_add_regulatory_source.sql",
    "004_add_dates.sql",
    "005_add_group_nodes.sql",
    "005_add_version_label.sql",
    "006_sources_config.sql",
    "007_harvest_doc_versioning.sql",
    "008_harvest_sources_external_id_unique.sql",
    "009_node_versioning.sql",
    "010_harvest_doc_is_latest.sql",
    "011_regulatory_document_versions.sql",
    "012_pgvector.sql",
    "013_add_sources_urls.sql",
    "014_doc_catalog.sql",
]

DROP_SQL = """
DROP TABLE IF EXISTS
    doc_sources,
    doc_domains,
    doc_categories,
    regulatory_document_versions,
    regulatory_node_versions,
    document_harvest_runs,
    regulatory_changes,
    regulatory_edges,
    regulatory_nodes,
    harvest_document_versions,
    harvest_documents,
    harvest_sources
CASCADE;

DROP TYPE IF EXISTS node_type CASCADE;
DROP TYPE IF EXISTS edge_type CASCADE;
"""


def reset_postgres() -> None:
    print("\n[PostgreSQL] Dropping all tables...")
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            cur.execute(DROP_SQL)
        conn.commit()
    print("  Tables dropped.")

    print("[PostgreSQL] Replaying migrations...")
    for fname in MIGRATION_FILES:
        fpath = MIGRATIONS_DIR / fname
        if not fpath.exists():
            print(f"  SKIP (not found): {fname}")
            continue
        sql = fpath.read_text(encoding="utf-8")
        # Migrations with embedded COMMIT/BEGIN must run with autocommit
        needs_autocommit = "COMMIT" in sql.upper() or "BEGIN" in sql.upper()
        try:
            conn = psycopg2.connect(settings.database_url_sync)
            conn.autocommit = needs_autocommit
            with conn.cursor() as cur:
                cur.execute(sql)
            if not needs_autocommit:
                conn.commit()
            conn.close()
            print(f"  Applied: {fname}")
        except Exception as e:
            print(f"  WARN {fname}: {e}")
    print("  PostgreSQL reset complete.")


def reset_chroma() -> None:
    print("\n[ChromaDB] Wiping vector store...")
    if CHROMA_PATH.exists():
        shutil.rmtree(CHROMA_PATH)
        print(f"  Deleted: {CHROMA_PATH}")
    else:
        print(f"  Nothing to delete at: {CHROMA_PATH}")
    print("  ChromaDB reset complete.")


def main() -> int:
    print("=" * 60)
    print("  FULL RESET — all data will be destroyed")
    print("=" * 60)
    confirm = input("Type 'yes' to confirm: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return 1

    reset_postgres()
    reset_chroma()

    print("\n✓ Reset complete. Re-run pdf_catalog.py and re-ingest sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
