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

    zip_path = target_dir / "package.zip"
    headers = {
        "User-Agent": USER_AGENT,
        "Referer": "https://www.easa.europa.eu/en/document-library/easy-access-rules",
        "Accept": "application/zip,application/octet-stream"
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=300) as resp, zip_path.open("wb") as out:  # noqa: S310
        while chunk := resp.read(1 << 20):
            out.write(chunk)

    with zipfile.ZipFile(zip_path) as zf:
        # Heuristic: look for the largest .xml OR any .docx file
        all_files = zf.infolist()
        xml_files = [f for f in all_files if f.filename.lower().endswith(".xml")]
        docx_files = [f for f in all_files if f.filename.lower().endswith(".docx")]

        if docx_files:
            # Save the .docx intact so the parser can access all parts:
            # customXml/item*.xml (er:toc) AND word/document.xml (body).
            # Extracting only the largest inner XML loses the TOC.
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
