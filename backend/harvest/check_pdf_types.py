"""Check which CS-25 PDFs are consolidated documents vs amendment deltas.

A consolidated PDF has hundreds of pages. A delta PDF has tens of pages.
We check page count via HTTP HEAD + partial download to detect this quickly.

Run:
    python -m uv run python -m backend.harvest.check_pdf_types
"""
from __future__ import annotations
import sys
import urllib.request
import pymupdf
import tempfile
from pathlib import Path

EASA_BASE = "https://www.easa.europa.eu"
USER_AGENT = "Mozilla/5.0"

CS25_VERSIONS = [
    ("Initial Issue", f"{EASA_BASE}/en/downloads/1516/en"),
    ("Amendment 1",   f"{EASA_BASE}/en/downloads/1561/en"),
    ("Amendment 2",   f"{EASA_BASE}/en/downloads/1563/en"),
    ("Amendment 3",   f"{EASA_BASE}/en/downloads/1566/en"),
    ("Amendment 4",   f"{EASA_BASE}/en/downloads/1569/en"),
    ("Amendment 5",   f"{EASA_BASE}/en/downloads/1572/en"),
    ("Amendment 6",   f"{EASA_BASE}/en/downloads/1575/en"),
    ("Amendment 7",   f"{EASA_BASE}/en/downloads/1578/en"),
    ("Amendment 8",   f"{EASA_BASE}/en/downloads/1581/en"),
    ("Amendment 9",   f"{EASA_BASE}/en/downloads/1584/en"),
    ("Amendment 10",  f"{EASA_BASE}/en/downloads/1587/en"),
    ("Amendment 11",  f"{EASA_BASE}/en/downloads/1590/en"),
    ("Amendment 12",  f"{EASA_BASE}/en/downloads/1714/en"),
    ("Amendment 13",  f"{EASA_BASE}/en/downloads/1982/en"),
    ("Amendment 14",  f"{EASA_BASE}/en/downloads/17500/en"),
    ("Amendment 15",  f"{EASA_BASE}/en/downloads/22035/en"),
    ("Amendment 17",  f"{EASA_BASE}/en/downloads/18864/en"),
    ("Amendment 18",  f"{EASA_BASE}/en/downloads/21117/en"),
    ("Amendment 19",  f"{EASA_BASE}/en/downloads/22504/en"),
    ("Amendment 20",  f"{EASA_BASE}/en/downloads/32288/en"),
    ("Amendment 21",  f"{EASA_BASE}/en/downloads/46017/en"),
    ("Amendment 22",  f"{EASA_BASE}/en/downloads/65402/en"),
    ("Amendment 23",  f"{EASA_BASE}/en/downloads/100573/en"),
    ("Amendment 24",  f"{EASA_BASE}/en/downloads/108354/en"),
    ("Amendment 25",  f"{EASA_BASE}/en/downloads/116279/en"),
    ("Amendment 26",  f"{EASA_BASE}/en/downloads/121128/en"),
    ("Amendment 27",  f"{EASA_BASE}/en/downloads/136622/en"),
    ("Amendment 28",  f"{EASA_BASE}/en/downloads/139073/en"),
]

# Already known
KNOWN = {
    "Amendment 27": ("delta", 17),
    "Amendment 28": ("consolidated", 1515),
}


def check_version(label: str, url: str) -> tuple[str, int, int]:
    """Returns (label, page_count, file_size_kb). Uses Content-Length for quick size check."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310
        size_kb = int(r.headers.get("Content-Length", 0)) // 1024
        # Read full file to get real size if Content-Length not provided
        if size_kb == 0:
            data = r.read()
            size_kb = len(data) // 1024
        else:
            data = r.read()

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(data)
        tmp = Path(f.name)

    try:
        doc = pymupdf.open(str(tmp))
        pages = doc.page_count
        doc.close()
    except Exception:
        pages = -1
    finally:
        tmp.unlink(missing_ok=True)

    return label, pages, size_kb


def main() -> int:
    print(f"{'Version':<20} {'Pages':>8} {'Size KB':>10} {'Type':>15}")
    print("-" * 60)

    for label, url in CS25_VERSIONS:
        if label in KNOWN:
            kind, pages = KNOWN[label]
            print(f"{label:<20} {pages:>8} {'(cached)':>10} {kind:>15}")
            continue
        try:
            _, pages, size_kb = check_version(label, url)
            kind = "consolidated" if pages > 200 else "delta" if pages > 0 else "unknown"
            print(f"{label:<20} {pages:>8} {size_kb:>10} {kind:>15}")
        except Exception as e:
            print(f"{label:<20} {'ERR':>8} {'':>10} {str(e)[:30]:>15}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
