"""Validation: compare PDF parser output vs XML parser output on equivalent CS-25 versions.

Compares Amendment 28 PDF (already downloaded) vs the XML from the current run.
Also optionally downloads Amendment 27 PDF and compares with the XML we have locally.

Run:
    python -m uv run python -m backend.harvest.validate_pdf_vs_xml
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

from backend.harvest.pdf_cs_parser import parse_cs_pdf
from backend.harvest.easa_parser import parse_easa_xml
from backend.harvest.models import ParseResult

EASA_BASE = "https://www.easa.europa.eu"
AM27_PDF_URL = f"{EASA_BASE}/en/downloads/136622/en"
AM28_PDF_PATH = Path("data/tmp_cs25_am28.pdf")
AM27_XML_PATH = Path("data/raw/easa/2026-04-12/easa-cs25/document.xml")
USER_AGENT = "Mozilla/5.0"


def _by_ref(result: ParseResult) -> dict[str, str]:
    """reference_code → content_text"""
    return {n.reference_code: n.content_text for n in result.nodes}


def _compare(label_a: str, a: ParseResult, label_b: str, b: ParseResult) -> None:
    refs_a = _by_ref(a)
    refs_b = _by_ref(b)
    keys_a = set(refs_a)
    keys_b = set(refs_b)

    only_a = keys_a - keys_b
    only_b = keys_b - keys_a
    common = keys_a & keys_b

    content_match = sum(1 for k in common if refs_a[k] == refs_b[k])
    content_diff  = sum(1 for k in common if refs_a[k] != refs_b[k])

    print(f"\n{'='*60}")
    print(f"  {label_a}  vs  {label_b}")
    print(f"{'='*60}")
    print(f"  Nodes in {label_a:10s}: {len(keys_a)}")
    print(f"  Nodes in {label_b:10s}: {len(keys_b)}")
    print(f"  Common refs       : {len(common)}")
    print(f"  Content identical : {content_match} / {len(common)}")
    print(f"  Content differs   : {content_diff} / {len(common)}")
    print(f"  Only in {label_a:10s}: {len(only_a)}")
    print(f"  Only in {label_b:10s}: {len(only_b)}")

    if only_a:
        print(f"\n  Sample only in {label_a} (up to 10):")
        for r in sorted(only_a)[:10]:
            print(f"    - {r!r}")

    if only_b:
        print(f"\n  Sample only in {label_b} (up to 10):")
        for r in sorted(only_b)[:10]:
            print(f"    - {r!r}")

    if content_diff:
        print(f"\n  Sample content differences (up to 5):")
        n = 0
        for k in sorted(common):
            if refs_a[k] != refs_b[k]:
                ta = (refs_a[k] or "")[:120].replace("\n", " ")
                tb = (refs_b[k] or "")[:120].replace("\n", " ")
                print(f"    [{k!r}]")
                print(f"      {label_a}: {ta!r}")
                print(f"      {label_b}: {tb!r}")
                n += 1
                if n >= 5:
                    break


def main() -> int:
    # ── 1. Parse AM28 PDF (already downloaded) ────────────────────────────────
    if not AM28_PDF_PATH.exists():
        print(f"ERROR: {AM28_PDF_PATH} not found. Run backfill or download manually.")
        return 1

    print(f"Parsing AM28 PDF: {AM28_PDF_PATH} ...")
    am28_pdf = parse_cs_pdf(AM28_PDF_PATH, regulatory_source="CS-25")
    print(f"  -> {len(am28_pdf.nodes)} nodes")

    # ── 2. Parse XML from current local run (same document base as AM27) ──────
    if AM27_XML_PATH.exists():
        print(f"\nParsing current XML: {AM27_XML_PATH} ...")
        xml_result = parse_easa_xml(AM27_XML_PATH)
        print(f"  -> {len(xml_result.nodes)} nodes  (version: {xml_result.source_version})")
        _compare("AM28-PDF", am28_pdf, "XML-current", xml_result)
    else:
        print(f"\nXML not found at {AM27_XML_PATH}, skipping XML comparison.")

    # ── 3. Download AM27 PDF and compare with AM28 PDF (version diff) ────────
    am27_pdf_path = Path("data/tmp_cs25_am27.pdf")
    if not am27_pdf_path.exists():
        print(f"\nDownloading AM27 PDF from {AM27_PDF_URL} ...")
        req = urllib.request.Request(AM27_PDF_URL, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=300) as r, am27_pdf_path.open("wb") as f:  # noqa: S310
            f.write(r.read())
        print(f"  Saved: {am27_pdf_path} ({am27_pdf_path.stat().st_size // 1024} KB)")
    else:
        print(f"\nAM27 PDF already at {am27_pdf_path}")

    print(f"Parsing AM27 PDF ...")
    am27_pdf = parse_cs_pdf(am27_pdf_path, regulatory_source="CS-25")
    print(f"  -> {len(am27_pdf.nodes)} nodes")

    _compare("AM27-PDF", am27_pdf, "AM28-PDF", am28_pdf)

    # ── 4. Summary ─────────────────────────────────────────────────────────────
    print("\n\n=== SUMMARY ===")
    print(f"  AM27 PDF nodes : {len(am27_pdf.nodes)}")
    print(f"  AM28 PDF nodes : {len(am28_pdf.nodes)}")
    if AM27_XML_PATH.exists():
        print(f"  XML curr nodes : {len(xml_result.nodes)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
