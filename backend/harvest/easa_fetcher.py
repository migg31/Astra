"""Fetch EASA regulatory documents (XML, HTML, PDF).

The rules are published as ZIP archives (containing Flat OPC XML or DOCX),
HTML online publications, or PDF files. We download the document,
cache it under `data/raw/easa/`, and return metadata.
"""
from __future__ import annotations

import hashlib
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

PART21_XML_ZIP_URL = "https://www.easa.europa.eu/en/downloads/136660/en"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

DocFormat = Literal["xml", "html", "pdf", "json"]

@dataclass
class FetchedDocument:
    path: Path
    content_hash: str
    fetched_at: datetime
    url: str
    external_id: str
    format: DocFormat


def _hash_file(path: Path) -> str:
    h = hashlib.md5()  # noqa: S324 — used for change detection, not security
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_easa_document(
    data_dir: Path,
    urls: dict[str, str],
    external_id: str,
) -> FetchedDocument:
    """Try to download a document from a list of URLs in order of priority (json > xml > html > pdf)."""

    # Local JSON — no download, just point to the file
    json_path_str = urls.get("json")
    if json_path_str:
        json_path = Path(json_path_str)
        if not json_path.is_absolute():
            json_path = data_dir / json_path_str
        if json_path.exists():
            return FetchedDocument(
                path=json_path,
                content_hash=_hash_file(json_path),
                fetched_at=datetime.now(timezone.utc),
                url=str(json_path),
                external_id=external_id,
                format="json",
            )
        raise RuntimeError(f"Local JSON not found: {json_path}")

    # Priority order for remote formats
    for fmt in ["xml", "html", "pdf"]:
        url = urls.get(fmt)
        if not url:
            continue
        try:
            return _download_and_process(data_dir, url, external_id, fmt)
        except Exception as e:
            print(f"  [fetch] failed to download {fmt} from {url}: {e}")
            continue

    raise RuntimeError(f"Could not download document for {external_id} from any provided URLs.")


def _download_and_process(
    data_dir: Path,
    url: str,
    external_id: str,
    fmt: str,
) -> FetchedDocument:
    fetched_at = datetime.now(timezone.utc)
    target_dir = data_dir / "raw" / "easa" / fetched_at.strftime("%Y-%m-%d") / external_id
    target_dir.mkdir(parents=True, exist_ok=True)

    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.easa.europa.eu/en/document-library/easy-access-rules",
        "Accept": "application/pdf,application/zip,application/octet-stream,text/html",
    }
    req = urllib.request.Request(url, headers=headers)

    raw_path = target_dir / "package.bin"
    with urllib.request.urlopen(req, timeout=300) as resp:  # noqa: S310
        content_type = resp.headers.get("Content-Type", "")
        with raw_path.open("wb") as out:
            while chunk := resp.read(1 << 20):
                out.write(chunk)

    # ── PDF ──────────────────────────────────────────────────────────────────
    if "pdf" in content_type.lower() or raw_path.read_bytes()[:4] == b"%PDF":
        pdf_path = target_dir / "document.pdf"
        raw_path.replace(pdf_path)
        return FetchedDocument(
            path=pdf_path,
            content_hash=_hash_file(pdf_path),
            fetched_at=fetched_at,
            url=url,
            external_id=external_id,
            format="pdf",
        )

    # ── HTML ─────────────────────────────────────────────────────────────────
    if "text/html" in content_type.lower() or fmt == "html":
        html_path = target_dir / "document.html"
        raw_path.replace(html_path)
        return FetchedDocument(
            path=html_path,
            content_hash=_hash_file(html_path),
            fetched_at=fetched_at,
            url=url,
            external_id=external_id,
            format="html",
        )

    # ── ZIP (XML or DOCX inside) ─────────────────────────────────────────────
    zip_path = target_dir / "package.zip"
    raw_path.replace(zip_path)

    with zipfile.ZipFile(zip_path) as zf:
        all_files = zf.infolist()
        xml_files = [f for f in all_files if f.filename.lower().endswith(".xml")]
        docx_files = [f for f in all_files if f.filename.lower().endswith(".docx")]

        if docx_files:
            main_docx = max(docx_files, key=lambda x: x.file_size)
            final_path = target_dir / "document.docx"
            with zf.open(main_docx.filename) as src, final_path.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            doc_format = "xml"  # We treat DOCX as XML since our parser handles both
        elif xml_files:
            main_xml_info = max(xml_files, key=lambda x: x.file_size)
            final_path = target_dir / "document.xml"
            with zf.open(main_xml_info.filename) as src, final_path.open("wb") as dst:
                while chunk := src.read(1 << 20):
                    dst.write(chunk)
            doc_format = "xml"
        else:
            raise RuntimeError(f"No suitable XML or DOCX file found in {zip_path}.")

    return FetchedDocument(
        path=final_path,
        content_hash=_hash_file(final_path),
        fetched_at=fetched_at,
        url=url,
        external_id=external_id,
        format=doc_format,
    )


# Keep legacy functions for backward compatibility if needed, or refactor callers
def fetch_easa_xml(data_dir: Path, url: str, external_id: str) -> FetchedDocument:
    return fetch_easa_document(data_dir, {"xml": url}, external_id)

def fetch_part21_xml(data_dir: Path) -> FetchedDocument:
    return fetch_easa_xml(data_dir, PART21_XML_ZIP_URL, "easa-part21")


import re as _re  # noqa: E402

_VERSION_PATTERNS = [
    _re.compile(r"Amendment\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Issue\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Revision\s+(\d+)", _re.IGNORECASE),
    _re.compile(r"Initial\s+Issue", _re.IGNORECASE),
]

@dataclass
class VersionCheckResult:
    source_url: str
    latest_version: str | None
    indexed_version: str | None
    is_outdated: bool
    checked_at: datetime


def check_latest_version(url: str, indexed_version: str | None) -> VersionCheckResult:
    checked_at = datetime.now(timezone.utc)
    latest_version: str | None = None

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
            raw = resp.read(32_768).decode("utf-8", errors="ignore")

        for pat in _VERSION_PATTERNS:
            m = pat.search(raw)
            if m:
                latest_version = m.group(0).strip()
                latest_version = latest_version[0].upper() + latest_version[1:]
                break
    except Exception:
        pass

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
