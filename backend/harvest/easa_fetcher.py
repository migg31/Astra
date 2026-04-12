"""Fetch the EASA Easy Access Rules XML package for Part 21.

The rules are published as a ZIP archive containing a single "Flat OPC" XML
file (a Word document in `pkg:package` form). We download the zip, extract the
inner XML to a dated directory under `data/raw/easa/`, and return the path.
"""
from __future__ import annotations

import hashlib
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PART21_XML_ZIP_URL = "https://www.easa.europa.eu/en/downloads/136660/en"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@dataclass
class FetchedDocument:
    path: Path
    content_hash: str
    fetched_at: datetime
    url: str
    external_id: str


def _hash_file(path: Path) -> str:
    h = hashlib.md5()  # noqa: S324 — used for change detection, not security
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_easa_xml(
    data_dir: Path,
    url: str,
    external_id: str,
) -> FetchedDocument:
    """Download an EASA XML zip, extract it, and return metadata.

    Files are written under `data_dir / "raw/easa" / YYYY-MM-DD / external_id /`.
    """
    fetched_at = datetime.now(timezone.utc)
    target_dir = data_dir / "raw" / "easa" / fetched_at.strftime("%Y-%m-%d") / external_id
    target_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.easa.europa.eu/en/document-library/easy-access-rules",
        "Accept": "application/pdf,application/zip,application/octet-stream",
    }
    req = urllib.request.Request(url, headers=headers)

    raw_path = target_dir / "package.bin"
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        content_type = resp.headers.get("Content-Type", "")
        with raw_path.open("wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)

    # ── PDF response (CS amendments, CS-ACNS) ────────────────────────────────
    if "pdf" in content_type.lower() or raw_path.read_bytes()[:4] == b"%PDF":
        pdf_path = target_dir / "document.pdf"
        raw_path.rename(pdf_path)
        return FetchedDocument(
            path=pdf_path,
            content_hash=_hash_file(pdf_path),
            fetched_at=fetched_at,
            url=url,
            external_id=external_id,
        )

    # ── ZIP response (EasyAccess Rules: DOCX or XML inside) ──────────────────
    zip_path = target_dir / "package.zip"
    raw_path.rename(zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        all_files = zf.infolist()
        xml_files = [f for f in all_files if f.filename.lower().endswith(".xml")]
        docx_files = [f for f in all_files if f.filename.lower().endswith(".docx")]

        if docx_files:
            main_docx = max(docx_files, key=lambda x: x.file_size)
            xml_path = target_dir / "document.docx"
            with zf.open(main_docx.filename) as src, xml_path.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        elif xml_files:
            main_xml_info = max(xml_files, key=lambda x: x.file_size)
            xml_path = target_dir / "document.xml"
            with zf.open(main_xml_info.filename) as src, xml_path.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
        else:
            raise RuntimeError(f"No suitable XML or DOCX file found in {zip_path}. Files: {[f.filename for f in all_files]}")

    return FetchedDocument(
        path=xml_path,
        content_hash=_hash_file(xml_path),
        fetched_at=fetched_at,
        url=url,
        external_id=external_id,
    )

def fetch_part21_xml(data_dir: Path) -> FetchedDocument:
    """Legacy wrapper for Part 21."""
    return fetch_easa_xml(data_dir, PART21_XML_ZIP_URL, "easa-part21")


import re as _re  # noqa: E402 — kept local to avoid polluting module namespace

_VERSION_PATTERNS = [
    _re.compile(r"Amendment\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Issue\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Revision\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Initial\s+Issue", _re.IGNORECASE),
]


@dataclass
class VersionCheckResult:
    source_url: str
    latest_version: str | None   # e.g. "Amendment 27"
    indexed_version: str | None  # from DB
    is_outdated: bool            # latest != indexed (both non-null)
    checked_at: datetime


def check_latest_version(url: str, indexed_version: str | None) -> VersionCheckResult:
    """Scrape the EASA download page to extract the current version label.

    Makes a single lightweight HTTP GET on the HTML page (not the ZIP).
    The version is extracted from the page title or visible heading text.
    Returns a VersionCheckResult with is_outdated=True if the online version
    differs from the indexed one.
    """
    checked_at = datetime.now(timezone.utc)
    latest_version: str | None = None

    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            # Read only first 32 KB — version info is always in the page head/hero
            raw = resp.read(32_768).decode("utf-8", errors="ignore")

        # Try each pattern against the page text
        for pat in _VERSION_PATTERNS:
            m = pat.search(raw)
            if m:
                latest_version = m.group(0).strip()
                # Normalize capitalisation
                latest_version = latest_version[0].upper() + latest_version[1:]
                break

    except Exception:
        pass  # Network error — return is_outdated=False conservatively

    is_outdated = (
        latest_version is not None
        and indexed_version is not None
        and latest_version.lower() != indexed_version.lower()
    )

    return VersionCheckResult(
        source_url=url,
        latest_version=latest_version,
        indexed_version=indexed_version,
        is_outdated=is_outdated,
        checked_at=checked_at,
    )
