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


def fetch_part21_xml(
    data_dir: Path,
    url: str = PART21_XML_ZIP_URL,
) -> FetchedDocument:
    """Download the Part 21 XML zip, extract it, and return metadata.

    Files are written under `data_dir / "raw/easa" / YYYY-MM-DD /`.
    """
    fetched_at = datetime.now(timezone.utc)
    target_dir = data_dir / "raw" / "easa" / fetched_at.strftime("%Y-%m-%d")
    target_dir.mkdir(parents=True, exist_ok=True)

    zip_path = target_dir / "part21.zip"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=300) as resp, zip_path.open("wb") as out:  # noqa: S310
        while chunk := resp.read(1 << 20):
            out.write(chunk)

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        if len(names) != 1:
            raise RuntimeError(f"expected one file in zip, got {names}")
        inner_name = names[0]
        xml_path = target_dir / "part21.xml"
        with zf.open(inner_name) as src, xml_path.open("wb") as dst:
            while chunk := src.read(1 << 20):
                dst.write(chunk)

    return FetchedDocument(
        path=xml_path,
        content_hash=_hash_file(xml_path),
        fetched_at=fetched_at,
        url=url,
        external_id="easa-part21-748-2012",
    )
