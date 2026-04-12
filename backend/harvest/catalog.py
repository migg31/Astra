"""
EASA Regulatory Catalog — static list of all known regulatory texts.
Each entry describes a document that may or may not be indexed in Astra.
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class CatalogEntry:
    id: str                        # Unique slug
    name: str                      # Display name
    short: str                     # Short label e.g. "CS-25"
    category: str                  # "basic" | "ir" | "cs" | "amcgm"
    domain: str                    # fine-grained domain (see DOMAIN_LABELS below)
    description: str
    easa_url: str                  # Official EASA page
    harvest_key: str | None = None # external_id in harvest_sources (if harvestable)
    doc_title_pattern: str | None = None  # ILIKE pattern to match harvest_documents.title
    ref_code_pattern: str | None = None   # Postgres regex on reference_code to count nodes for this specific Part


CATALOG: list[CatalogEntry] = [
    # ── Basic Regulation ──────────────────────────────────────────────────────
    CatalogEntry(
        id="basic-reg",
        name="Basic Regulation — EU 2018/1139",
        short="EU 2018/1139",
        category="basic",
        domain="framework",
        description="Framework regulation establishing EASA's remit and powers.",
        easa_url="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32018R1139",
    ),

    # ── Implementing Rules — Initial Airworthiness ────────────────────────────
    CatalogEntry(
        id="part-21",
        name="Part 21 — Certification of Aircraft & Products",
        short="Part 21",
        category="ir",
        domain="initial-airworthiness",
        description="Implementing rules for certification of aircraft, engines, propellers and parts.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-part-21-edition-22",
        doc_title_pattern="%Initial Airworthiness%",
    ),
    CatalogEntry(
        id="part-26",
        name="Part 26 — Additional Airworthiness Requirements",
        short="Part 26",
        category="ir",
        domain="initial-airworthiness",
        description="Additional airworthiness requirements for operations.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-additional-airworthiness-specifications-2",
        doc_title_pattern="%Additional Airworthiness%",
    ),

    # ── Implementing Rules — Continuing Airworthiness ─────────────────────────
    CatalogEntry(
        id="part-m",
        name="Part M — Continuing Airworthiness",
        short="Part M",
        category="ir",
        domain="continuing-airworthiness",
        description="Requirements for continuing airworthiness management.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-continuing-airworthiness",
        doc_title_pattern="%Continuing Airworthiness%",
        ref_code_pattern=r"\yM\.",
    ),
    CatalogEntry(
        id="part-145",
        name="Part 145 — Maintenance Organisations",
        short="Part 145",
        category="ir",
        domain="continuing-airworthiness",
        description="Requirements for approved maintenance organisations.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-continuing-airworthiness",
        doc_title_pattern="%Continuing Airworthiness%",
        ref_code_pattern=r"\y145\.",
    ),
    CatalogEntry(
        id="part-66",
        name="Part 66 — Maintenance Licensing",
        short="Part 66",
        category="ir",
        domain="continuing-airworthiness",
        description="Requirements for certifying staff licensing.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-continuing-airworthiness",
        doc_title_pattern="%Continuing Airworthiness%",
        ref_code_pattern=r"\y66\.",
    ),
    CatalogEntry(
        id="part-camo",
        name="Part CAMO — Continuing Airworthiness Mgmt Org.",
        short="Part CAMO",
        category="ir",
        domain="continuing-airworthiness",
        description="Requirements for continuing airworthiness management organisations.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-continuing-airworthiness",
        doc_title_pattern="%Continuing Airworthiness%",
        ref_code_pattern=r"\yCAMO\.",
    ),

    # ── Implementing Rules — Air Operations ───────────────────────────────────
    CatalogEntry(
        id="part-oro",
        name="Part ORO — Organisation Requirements",
        short="Part ORO",
        category="ir",
        domain="air-operations",
        description="Organisational requirements for air operators.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-air-operations-eu-no-9652012",
        doc_title_pattern="%Air Operations%",
        ref_code_pattern=r"\yORO\.",
    ),
    CatalogEntry(
        id="part-cat",
        name="Part CAT — Commercial Air Transport",
        short="Part CAT",
        category="ir",
        domain="air-operations",
        description="Requirements for commercial air transport operations.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-air-operations-eu-no-9652012",
        doc_title_pattern="%Air Operations%",
        ref_code_pattern=r"\yCAT\.",
    ),
    CatalogEntry(
        id="part-spa",
        name="Part SPA — Specific Approvals",
        short="Part SPA",
        category="ir",
        domain="air-operations",
        description="Requirements for specific approvals (RVSM, MNPS, ETOPS, etc.).",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-air-operations-eu-no-9652012",
        doc_title_pattern="%Air Operations%",
        ref_code_pattern=r"\ySPA\.",
    ),

    # ── Implementing Rules — Aerodromes ──────────────────────────────────────
    CatalogEntry(
        id="part-adr",
        name="Part ADR — Aerodromes",
        short="Part ADR",
        category="ir",
        domain="aerodromes",
        description="Requirements for aerodrome design, operations and certification.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-aerodromes-regulation-eu-no-1392014",
        doc_title_pattern="%Aerodromes%",
    ),

    # ── Implementing Rules — Aircrew ──────────────────────────────────────────
    CatalogEntry(
        id="part-fcl",
        name="Part FCL — Flight Crew Licensing",
        short="Part FCL",
        category="ir",
        domain="aircrew",
        description="Requirements for pilot licences and ratings.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-flight-crew-licensing-eu-no-11782011",
    ),
    CatalogEntry(
        id="part-med",
        name="Part MED — Medical",
        short="Part MED",
        category="ir",
        domain="aircrew",
        description="Medical requirements for flight crew.",
        easa_url="https://www.easa.europa.eu/en/document-library/easy-access-rules/easy-access-rules-flight-crew-licensing-eu-no-11782011",
    ),

    # ── Certification Specifications — Fixed Wing ─────────────────────────────
    CatalogEntry(
        id="cs-25",
        name="CS-25 — Large Aeroplanes",
        short="CS-25",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for large aeroplanes (MTOW > 5 700 kg).",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-25-amendment-27",
        doc_title_pattern="CS-25%",
    ),
    CatalogEntry(
        id="cs-23",
        name="CS-23 — Normal-Category Aeroplanes",
        short="CS-23",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for normal-category aeroplanes.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-23-amendment-5",
    ),
    CatalogEntry(
        id="cs-27",
        name="CS-27 — Small Rotorcraft",
        short="CS-27",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for small rotorcraft (MTOW ≤ 3 175 kg).",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-27-amendment-10",
    ),
    CatalogEntry(
        id="cs-29",
        name="CS-29 — Large Rotorcraft",
        short="CS-29",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for large rotorcraft.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-29-amendment-10",
    ),
    CatalogEntry(
        id="cs-e",
        name="CS-E — Engines",
        short="CS-E",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for aircraft engines.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-e-amendment-6",
    ),
    CatalogEntry(
        id="cs-p",
        name="CS-P — Propellers",
        short="CS-P",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for propellers.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-p-amendment-5",
    ),
    CatalogEntry(
        id="cs-apu",
        name="CS-APU — Auxiliary Power Units",
        short="CS-APU",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for APUs.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-apu-initial-issue",
    ),
    CatalogEntry(
        id="cs-lsa",
        name="CS-LSA — Light Sport Aeroplanes",
        short="CS-LSA",
        category="cs",
        domain="initial-airworthiness",
        description="Certification specifications for light sport aeroplanes.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-lsa-amendment-1",
    ),

    # ── Certification Specifications — Avionics / CNS ────────────────────────
    CatalogEntry(
        id="cs-acns",
        name="CS-ACNS — Airborne Com/Nav/Surv",
        short="CS-ACNS",
        category="cs",
        domain="avionics",
        description="Certification specifications for airborne communications, navigation and surveillance.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-acns-issue-4",
        doc_title_pattern="CS-ACNS %",
    ),
    CatalogEntry(
        id="cs-awo",
        name="CS-AWO — All Weather Operations",
        short="CS-AWO",
        category="cs",
        domain="avionics",
        description="Certification specifications for all weather operations (PDF only — no XML available).",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-awo-amendment-3",
    ),
    CatalogEntry(
        id="cs-etso",
        name="CS-ETSO — Technical Standard Orders",
        short="CS-ETSO",
        category="cs",
        domain="avionics",
        description="Technical standard orders for airborne equipment.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-etso-amendment-20",
    ),
    CatalogEntry(
        id="cs-fcd",
        name="CS-FCD — Flight Crew Data",
        short="CS-FCD",
        category="cs",
        domain="avionics",
        description="Certification specifications for flight crew data.",
        easa_url="https://www.easa.europa.eu/en/document-library/certification-specifications/cs-fcd-initial-issue",
    ),
]

CATALOG_BY_ID: dict[str, CatalogEntry] = {e.id: e for e in CATALOG}
