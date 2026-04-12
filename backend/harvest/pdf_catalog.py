"""Populate regulatory_document_versions with all known PDF and XML versions.

Run with:
    python -m uv run python -m backend.harvest.pdf_catalog [--source cs-25|cs-acns|all]

This script does NOT parse nodes — it only registers versions in the catalog.
The is_indexed flag is set based on what is currently in harvest_documents.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date

import psycopg2
from backend.config import settings

EASA = "https://www.easa.europa.eu"

# ── CS-25 ─────────────────────────────────────────────────────────────────────
CS25_VERSIONS: list[dict] = [
    {"version_label": "Initial Issue", "url": f"{EASA}/en/downloads/1516/en",   "pub_date": date(2003, 10, 14), "doc_type": "pdf"},
    {"version_label": "Amendment 1",   "url": f"{EASA}/en/downloads/1561/en",   "pub_date": date(2004,  3, 24), "doc_type": "pdf"},
    {"version_label": "Amendment 2",   "url": f"{EASA}/en/downloads/1563/en",   "pub_date": date(2004,  3, 24), "doc_type": "pdf"},
    {"version_label": "Amendment 3",   "url": f"{EASA}/en/downloads/1566/en",   "pub_date": date(2006,  7, 14), "doc_type": "pdf"},
    {"version_label": "Amendment 4",   "url": f"{EASA}/en/downloads/1569/en",   "pub_date": date(2007,  9, 28), "doc_type": "pdf"},
    {"version_label": "Amendment 5",   "url": f"{EASA}/en/downloads/1572/en",   "pub_date": date(2008,  7, 25), "doc_type": "pdf"},
    {"version_label": "Amendment 6",   "url": f"{EASA}/en/downloads/1575/en",   "pub_date": date(2009,  5, 22), "doc_type": "pdf"},
    {"version_label": "Amendment 7",   "url": f"{EASA}/en/downloads/1578/en",   "pub_date": date(2010,  3, 31), "doc_type": "pdf"},
    {"version_label": "Amendment 8",   "url": f"{EASA}/en/downloads/1581/en",   "pub_date": date(2010, 11, 19), "doc_type": "pdf"},
    {"version_label": "Amendment 9",   "url": f"{EASA}/en/downloads/1584/en",   "pub_date": date(2011,  7, 15), "doc_type": "pdf"},
    {"version_label": "Amendment 10",  "url": f"{EASA}/en/downloads/1587/en",   "pub_date": date(2012,  1, 20), "doc_type": "pdf"},
    {"version_label": "Amendment 11",  "url": f"{EASA}/en/downloads/1590/en",   "pub_date": date(2012,  7, 20), "doc_type": "pdf"},
    {"version_label": "Amendment 12",  "url": f"{EASA}/en/downloads/1714/en",   "pub_date": date(2013,  1, 11), "doc_type": "pdf"},
    {"version_label": "Amendment 13",  "url": f"{EASA}/en/downloads/1982/en",   "pub_date": date(2013,  7, 26), "doc_type": "pdf"},
    {"version_label": "Amendment 14",  "url": f"{EASA}/en/downloads/17500/en",  "pub_date": date(2014,  1, 10), "doc_type": "pdf"},
    {"version_label": "Amendment 15",  "url": f"{EASA}/en/downloads/22035/en",  "pub_date": date(2014,  7, 18), "doc_type": "pdf"},
    {"version_label": "Amendment 16",  "url": f"{EASA}/en/downloads/22035/en",  "pub_date": date(2015,  3, 27), "doc_type": "pdf"},
    {"version_label": "Amendment 17",  "url": f"{EASA}/en/downloads/18864/en",  "pub_date": date(2015, 10,  2), "doc_type": "pdf"},
    {"version_label": "Amendment 18",  "url": f"{EASA}/en/downloads/21117/en",  "pub_date": date(2016,  3, 18), "doc_type": "pdf"},
    {"version_label": "Amendment 19",  "url": f"{EASA}/en/downloads/22504/en",  "pub_date": date(2016,  8, 19), "doc_type": "pdf"},
    {"version_label": "Amendment 20",  "url": f"{EASA}/en/downloads/32288/en",  "pub_date": date(2017,  3, 31), "doc_type": "pdf"},
    {"version_label": "Amendment 21",  "url": f"{EASA}/en/downloads/46017/en",  "pub_date": date(2017, 12, 22), "doc_type": "pdf"},
    {"version_label": "Amendment 22",  "url": f"{EASA}/en/downloads/65402/en",  "pub_date": date(2018, 10, 26), "doc_type": "pdf"},
    {"version_label": "Amendment 23",  "url": f"{EASA}/en/downloads/100573/en", "pub_date": date(2020,  5, 15), "doc_type": "pdf"},
    {"version_label": "Amendment 24",  "url": f"{EASA}/en/downloads/108354/en", "pub_date": date(2020, 10, 23), "doc_type": "pdf"},
    {"version_label": "Amendment 25",  "url": f"{EASA}/en/downloads/116279/en", "pub_date": date(2021,  7, 16), "doc_type": "pdf"},
    {"version_label": "Amendment 26",  "url": f"{EASA}/en/downloads/121128/en", "pub_date": date(2022,  7, 22), "doc_type": "pdf"},
    {"version_label": "Amendment 27",  "url": f"{EASA}/en/downloads/135090/en", "pub_date": date(2023,  4, 21), "doc_type": "pdf"},
    {"version_label": "Amendment 28",  "url": f"{EASA}/en/downloads/139073/en", "pub_date": date(2024,  1, 26), "doc_type": "pdf", "is_latest_pdf": True},
    # XML Easy Access Rules (machine-readable) — corresponds to Am27 content
    {"version_label": "Amendment 27",  "url": f"{EASA}/en/downloads/136662/en", "pub_date": date(2023,  4, 21), "doc_type": "xml"},
]

CS25_SOURCE = {
    "source_key": "cs-25",
    "source_label": "CS-25 \u2014 Large Aeroplanes",
    "versions": CS25_VERSIONS,
    "xml_external_id": "easa-cs25",
}

# ── CS-ACNS ───────────────────────────────────────────────────────────────────
CSACNS_VERSIONS: list[dict] = [
    {"version_label": "Initial Issue", "url": f"{EASA}/en/downloads/16743/en",  "pub_date": date(2011,  3, 22), "doc_type": "pdf"},
    {"version_label": "Issue 2",       "url": f"{EASA}/en/downloads/96591/en",  "pub_date": date(2016,  3, 18), "doc_type": "pdf"},
    {"version_label": "Issue 3",       "url": f"{EASA}/en/downloads/128205/en", "pub_date": date(2019,  7, 19), "doc_type": "pdf"},
    {"version_label": "Issue 4",       "url": f"{EASA}/en/downloads/136330/en", "pub_date": date(2021, 11, 26), "doc_type": "pdf"},
    {"version_label": "Issue 5",       "url": f"{EASA}/en/downloads/139873/en", "pub_date": date(2023,  7, 21), "doc_type": "pdf", "is_latest_pdf": True},
    # XML Easy Access Rules — the harvester fetches Issue 4 XML (136674); Issue 5 XML not yet published
    {"version_label": "Issue 4",       "url": f"{EASA}/en/downloads/136674/en", "pub_date": date(2022,  4,  6), "doc_type": "xml"},
]

CSACNS_SOURCE = {
    "source_key": "cs-acns",
    "source_label": "CS-ACNS \u2014 Airborne Communications, Navigation and Surveillance",
    "versions": CSACNS_VERSIONS,
    "xml_external_id": "easa-csacns",
}

# ── Part 21 ───────────────────────────────────────────────────────────────────
PART21_SOURCE = {
    "source_key": "part-21",
    "source_label": "Part 21 \u2014 Certification of Aircraft & Products",
    "xml_external_id": "easa-part21",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/1690/en",   "pub_date": date(2003, 11, 28), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/17501/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 3",   "url": f"{EASA}/en/downloads/43827/en",  "pub_date": date(2017,  8,  4), "doc_type": "pdf"},
        {"version_label": "Edition 4",   "url": f"{EASA}/en/downloads/98649/en",  "pub_date": date(2020,  3,  5), "doc_type": "pdf"},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/117041/en", "pub_date": date(2021,  8, 31), "doc_type": "pdf"},
        {"version_label": "Edition 6",   "url": f"{EASA}/en/downloads/127921/en", "pub_date": date(2022,  8,  2), "doc_type": "pdf"},
        {"version_label": "Edition 7",   "url": f"{EASA}/en/downloads/136327/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf"},
        {"version_label": "Edition 8",   "url": f"{EASA}/en/downloads/139004/en", "pub_date": date(2024,  3, 28), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 8",   "url": f"{EASA}/en/downloads/139004/en", "pub_date": date(2024,  3, 28), "doc_type": "xml"},
    ],
}

# ── Part 26 ───────────────────────────────────────────────────────────────────
PART26_SOURCE = {
    "source_key": "part-26",
    "source_label": "Part 26 \u2014 Additional Airworthiness Requirements",
    "xml_external_id": "easa-part26",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/17517/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/137034/en", "pub_date": date(2023,  7, 31), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/137034/en", "pub_date": date(2023,  7, 31), "doc_type": "xml"},
    ],
}

# ── Continuing Airworthiness (M, 145, 66, CAMO) ───────────────────────────────
CONT_AW_SOURCE = {
    "source_key": "continuing-airworthiness",
    "source_label": "Continuing Airworthiness \u2014 Parts M, 145, 66, CAMO",
    "xml_external_id": "easa-airworthiness",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/17508/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/65406/en",  "pub_date": date(2018, 11,  9), "doc_type": "pdf"},
        {"version_label": "Edition 3",   "url": f"{EASA}/en/downloads/98655/en",  "pub_date": date(2020,  3,  5), "doc_type": "pdf"},
        {"version_label": "Edition 4",   "url": f"{EASA}/en/downloads/117050/en", "pub_date": date(2021,  8, 31), "doc_type": "pdf"},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136328/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf"},
        {"version_label": "Edition 6",   "url": f"{EASA}/en/downloads/139006/en", "pub_date": date(2024,  3, 28), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 6",   "url": f"{EASA}/en/downloads/139006/en", "pub_date": date(2024,  3, 28), "doc_type": "xml"},
    ],
}

# ── Air Operations (ORO, CAT, SPA) ────────────────────────────────────────────
AIR_OPS_SOURCE = {
    "source_key": "air-operations",
    "source_label": "Air Operations \u2014 Parts ORO, CAT, SPA",
    "xml_external_id": "easa-ops",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/17505/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/65404/en",  "pub_date": date(2018, 11,  9), "doc_type": "pdf"},
        {"version_label": "Edition 3",   "url": f"{EASA}/en/downloads/98651/en",  "pub_date": date(2020,  3,  5), "doc_type": "pdf"},
        {"version_label": "Edition 4",   "url": f"{EASA}/en/downloads/117044/en", "pub_date": date(2021,  8, 31), "doc_type": "pdf"},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136329/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf"},
        {"version_label": "Edition 6",   "url": f"{EASA}/en/downloads/139007/en", "pub_date": date(2024,  3, 28), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 6",   "url": f"{EASA}/en/downloads/139007/en", "pub_date": date(2024,  3, 28), "doc_type": "xml"},
    ],
}

# ── Aerodromes (ADR) ──────────────────────────────────────────────────────────
AERODROMES_SOURCE = {
    "source_key": "part-adr",
    "source_label": "Part ADR \u2014 Aerodromes",
    "xml_external_id": "easa-aerodromes",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/17515/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/65408/en",  "pub_date": date(2018, 11,  9), "doc_type": "pdf"},
        {"version_label": "Edition 3",   "url": f"{EASA}/en/downloads/98657/en",  "pub_date": date(2020,  3,  5), "doc_type": "pdf"},
        {"version_label": "Edition 4",   "url": f"{EASA}/en/downloads/117052/en", "pub_date": date(2021,  8, 31), "doc_type": "pdf"},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136331/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136331/en", "pub_date": date(2023,  6, 30), "doc_type": "xml"},
    ],
}

# ── Aircrew (FCL, MED) ────────────────────────────────────────────────────────
AIRCREW_SOURCE = {
    "source_key": "aircrew",
    "source_label": "Aircrew \u2014 Parts FCL, MED",
    "xml_external_id": "easa-aircrew",
    "versions": [
        {"version_label": "Edition 1",   "url": f"{EASA}/en/downloads/17506/en",  "pub_date": date(2014,  1, 16), "doc_type": "pdf"},
        {"version_label": "Edition 2",   "url": f"{EASA}/en/downloads/65405/en",  "pub_date": date(2018, 11,  9), "doc_type": "pdf"},
        {"version_label": "Edition 3",   "url": f"{EASA}/en/downloads/98653/en",  "pub_date": date(2020,  3,  5), "doc_type": "pdf"},
        {"version_label": "Edition 4",   "url": f"{EASA}/en/downloads/117046/en", "pub_date": date(2021,  8, 31), "doc_type": "pdf"},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136325/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf", "is_latest_pdf": True},
        {"version_label": "Edition 5",   "url": f"{EASA}/en/downloads/136325/en", "pub_date": date(2023,  6, 30), "doc_type": "xml"},
    ],
}

# ── CS-23 (PDF only) ──────────────────────────────────────────────────────────
CS23_SOURCE = {
    "source_key": "cs-23",
    "source_label": "CS-23 \u2014 Normal-Category Aeroplanes",
    "xml_external_id": None,
    "versions": [
        {"version_label": "Initial Issue", "url": f"{EASA}/en/downloads/1597/en",   "pub_date": date(2003, 11, 14), "doc_type": "pdf"},
        {"version_label": "Amendment 1",   "url": f"{EASA}/en/downloads/1598/en",   "pub_date": date(2006,  7, 14), "doc_type": "pdf"},
        {"version_label": "Amendment 2",   "url": f"{EASA}/en/downloads/1600/en",   "pub_date": date(2008,  7, 25), "doc_type": "pdf"},
        {"version_label": "Amendment 3",   "url": f"{EASA}/en/downloads/1602/en",   "pub_date": date(2012,  7, 20), "doc_type": "pdf"},
        {"version_label": "Amendment 4",   "url": f"{EASA}/en/downloads/1604/en",   "pub_date": date(2015,  3, 27), "doc_type": "pdf"},
        {"version_label": "Amendment 5",   "url": f"{EASA}/en/downloads/116249/en", "pub_date": date(2021,  7, 16), "doc_type": "pdf", "is_latest_pdf": True},
    ],
}

# ── CS-27 (PDF only) ──────────────────────────────────────────────────────────
CS27_SOURCE = {
    "source_key": "cs-27",
    "source_label": "CS-27 \u2014 Small Rotorcraft",
    "xml_external_id": None,
    "versions": [
        {"version_label": "Initial Issue", "url": f"{EASA}/en/downloads/1606/en",   "pub_date": date(2003, 11, 14), "doc_type": "pdf"},
        {"version_label": "Amendment 1",   "url": f"{EASA}/en/downloads/1608/en",   "pub_date": date(2007,  9, 28), "doc_type": "pdf"},
        {"version_label": "Amendment 2",   "url": f"{EASA}/en/downloads/1610/en",   "pub_date": date(2010,  3, 31), "doc_type": "pdf"},
        {"version_label": "Amendment 3",   "url": f"{EASA}/en/downloads/1612/en",   "pub_date": date(2012,  7, 20), "doc_type": "pdf"},
        {"version_label": "Amendment 4",   "url": f"{EASA}/en/downloads/17494/en",  "pub_date": date(2014,  1, 10), "doc_type": "pdf"},
        {"version_label": "Amendment 5",   "url": f"{EASA}/en/downloads/22067/en",  "pub_date": date(2014,  7, 18), "doc_type": "pdf"},
        {"version_label": "Amendment 6",   "url": f"{EASA}/en/downloads/116252/en", "pub_date": date(2021,  7, 16), "doc_type": "pdf"},
        {"version_label": "Amendment 7",   "url": f"{EASA}/en/downloads/136324/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf", "is_latest_pdf": True},
    ],
}

# ── CS-29 (PDF only) ──────────────────────────────────────────────────────────
CS29_SOURCE = {
    "source_key": "cs-29",
    "source_label": "CS-29 \u2014 Large Rotorcraft",
    "xml_external_id": None,
    "versions": [
        {"version_label": "Initial Issue", "url": f"{EASA}/en/downloads/1614/en",   "pub_date": date(2003, 11, 14), "doc_type": "pdf"},
        {"version_label": "Amendment 1",   "url": f"{EASA}/en/downloads/1616/en",   "pub_date": date(2007,  9, 28), "doc_type": "pdf"},
        {"version_label": "Amendment 2",   "url": f"{EASA}/en/downloads/1618/en",   "pub_date": date(2010,  3, 31), "doc_type": "pdf"},
        {"version_label": "Amendment 3",   "url": f"{EASA}/en/downloads/1620/en",   "pub_date": date(2012,  7, 20), "doc_type": "pdf"},
        {"version_label": "Amendment 4",   "url": f"{EASA}/en/downloads/17496/en",  "pub_date": date(2014,  1, 10), "doc_type": "pdf"},
        {"version_label": "Amendment 5",   "url": f"{EASA}/en/downloads/22069/en",  "pub_date": date(2014,  7, 18), "doc_type": "pdf"},
        {"version_label": "Amendment 6",   "url": f"{EASA}/en/downloads/116255/en", "pub_date": date(2021,  7, 16), "doc_type": "pdf"},
        {"version_label": "Amendment 7",   "url": f"{EASA}/en/downloads/136323/en", "pub_date": date(2023,  6, 30), "doc_type": "pdf", "is_latest_pdf": True},
    ],
}

ALL_SOURCES = [
    CS25_SOURCE, CSACNS_SOURCE,
    PART21_SOURCE, PART26_SOURCE,
    CONT_AW_SOURCE, AIR_OPS_SOURCE, AERODROMES_SOURCE, AIRCREW_SOURCE,
    CS23_SOURCE, CS27_SOURCE, CS29_SOURCE,
]


def populate(source: dict, conn) -> None:
    key = source["source_key"]
    label = source["source_label"]
    xml_ext_id = source.get("xml_external_id")

    with conn.cursor() as cur:
        # Resolve xml_doc_id from harvest_documents if available
        xml_doc_id = None
        if xml_ext_id:
            cur.execute(
                "SELECT doc_id FROM harvest_documents hd "
                "JOIN harvest_sources hs ON hd.source_id = hs.source_id "
                "WHERE hs.external_id = %s AND hd.is_latest = TRUE "
                "ORDER BY hd.fetched_at DESC LIMIT 1",
                (xml_ext_id,),
            )
            row = cur.fetchone()
            if row:
                xml_doc_id = row[0]

        has_xml = any(v["doc_type"] == "xml" for v in source["versions"])

        for v in source["versions"]:
            is_latest_pdf = v.get("is_latest_pdf", False)
            if v["doc_type"] == "xml":
                is_indexed = True                   # XML always indexed
            elif not has_xml and is_latest_pdf:
                is_indexed = True                   # PDF indexed only when no XML exists at all
            else:
                is_indexed = False                  # PDF never indexed when XML present

            cur.execute(
                """
                INSERT INTO regulatory_document_versions
                    (source_key, source_label, version_label, pub_date, url,
                     doc_type, is_indexed, is_latest_pdf, xml_doc_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_key, version_label, doc_type) DO UPDATE
                    SET pub_date      = EXCLUDED.pub_date,
                        url           = EXCLUDED.url,
                        is_indexed    = EXCLUDED.is_indexed,
                        is_latest_pdf = EXCLUDED.is_latest_pdf,
                        xml_doc_id    = COALESCE(EXCLUDED.xml_doc_id,
                                                 regulatory_document_versions.xml_doc_id)
                """,
                (key, label, v["version_label"], v.get("pub_date"),
                 v["url"], v["doc_type"], is_indexed, is_latest_pdf,
                 xml_doc_id if v["doc_type"] == "xml" else None),
            )
        print(f"  {key}: {len(source['versions'])} versions registered"
              + (f" (xml_doc_id={xml_doc_id})" if xml_doc_id else " (no XML doc linked)"))
    conn.commit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    all_keys = [s["source_key"] for s in ALL_SOURCES]
    parser.add_argument("--source", choices=all_keys + ["all"], default="all")
    args = parser.parse_args(argv)

    sources = ALL_SOURCES if args.source == "all" else [
        s for s in ALL_SOURCES if s["source_key"] == args.source
    ]

    with psycopg2.connect(settings.database_url_sync) as conn:
        for source in sources:
            print(f"\n[{source['source_key']}] Populating catalog...")
            populate(source, conn)

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
