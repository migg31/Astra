"""Seed doc_categories, doc_domains, doc_sources from catalog.py data.

Run with:
    python -m uv run python -m backend.database.seed_catalog

Idempotent: safe to re-run (uses ON CONFLICT DO UPDATE).
"""
from __future__ import annotations

import sys
import psycopg2
from backend.config import settings
from backend.harvest.catalog import CATALOG

CATEGORIES = [
    ("basic",  "Basic Regulation",    1),
    ("ir",     "Implementing Rules",  2),
    ("cs",     "Certification Specs", 3),
    ("amcgm",  "AMC & GM",            4),
    ("other",  "Other",               5),
]

DOMAINS = [
    ("framework",               "Framework",                        1),
    ("initial-airworthiness",   "Initial Airworthiness",            2),
    ("continuing-airworthiness","Continuing Airworthiness",         3),
    ("air-operations",          "Air Operations",                   4),
    ("aerodromes",              "Aerodromes",                       5),
    ("aircrew",                 "Aircrew",                          6),
    ("avionics",                "Avionics / CNS / All-Weather",     7),
    ("other",                   "Other",                            8),
]


def seed(conn) -> None:
    with conn.cursor() as cur:
        # ── Categories ────────────────────────────────────────────────────────
        for cat_id, label, order in CATEGORIES:
            cur.execute(
                """
                INSERT INTO doc_categories (id, label, sort_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET label = EXCLUDED.label,
                        sort_order = EXCLUDED.sort_order
                """,
                (cat_id, label, order),
            )
        print(f"  doc_categories: {len(CATEGORIES)} rows seeded")

        # ── Domains ───────────────────────────────────────────────────────────
        for dom_id, label, order in DOMAINS:
            cur.execute(
                """
                INSERT INTO doc_domains (id, label, sort_order)
                VALUES (%s, %s, %s)
                ON CONFLICT (id) DO UPDATE
                    SET label = EXCLUDED.label,
                        sort_order = EXCLUDED.sort_order
                """,
                (dom_id, label, order),
            )
        print(f"  doc_domains: {len(DOMAINS)} rows seeded")

        # ── doc_sources from catalog.py ───────────────────────────────────────
        # Map catalog.py harvest_key → real harvest_sources.external_id
        # catalog.py uses short slugs; harvest_sources uses "easa-*" prefixed ids.
        HARVEST_KEY_MAP: dict[str, str] = {
            "part-21":                  "easa-part21",
            "part-26":                  "easa-part26",
            "continuing-airworthiness": "easa-airworthiness",
            "air-operations":           "easa-ops",
            "part-adr":                 "easa-aerodromes",
            "aircrew":                  "easa-aircrew",
            "cs-25":                    "easa-cs25",
            "cs-acns":                  "easa-csacns",
        }

        cur.execute("SELECT external_id FROM source_files WHERE enabled = TRUE")
        active_keys = {r[0] for r in cur.fetchall()}

        for i, entry in enumerate(CATALOG):
            # Resolve real external_id (use mapping if available, else keep as-is)
            resolved_key = HARVEST_KEY_MAP.get(entry.harvest_key, entry.harvest_key) if entry.harvest_key else None
            cur.execute(
                """
                INSERT INTO regulations
                    (id, name, short, category_id, domain_id, description,
                     easa_url, harvest_key, doc_title_pattern, ref_code_pattern,
                     is_active, sort_order)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (id) DO UPDATE
                    SET name               = EXCLUDED.name,
                        short              = EXCLUDED.short,
                        category_id        = EXCLUDED.category_id,
                        domain_id          = EXCLUDED.domain_id,
                        description        = EXCLUDED.description,
                        easa_url           = EXCLUDED.easa_url,
                        harvest_key        = EXCLUDED.harvest_key,
                        doc_title_pattern  = EXCLUDED.doc_title_pattern,
                        ref_code_pattern   = EXCLUDED.ref_code_pattern,
                        sort_order         = EXCLUDED.sort_order,
                        updated_at         = NOW()
                """,
                (
                    entry.id,
                    entry.name,
                    entry.short,
                    entry.category,
                    entry.domain,
                    entry.description,
                    entry.easa_url,
                    resolved_key,
                    entry.doc_title_pattern,
                    entry.ref_code_pattern,
                    True,  # all active by default; admin can toggle
                    i,
                ),
            )
        print(f"  regulations: {len(CATALOG)} rows seeded")
    conn.commit()


def main() -> int:
    with psycopg2.connect(settings.database_url_sync) as conn:
        seed(conn)
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
