"""Parse EASA Online Publications (HTML) and produce regulatory nodes.

The EASA website uses a specific structure for its "Online publications":
- Articles are usually within <div> elements with specific classes or IDs.
- IR/AMC/GM/CS are often visually distinguished.
- Hierarchy is represented by nested structures or heading levels.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from bs4 import BeautifulSoup

from backend.harvest.models import ParsedNode, ParsedEdge, ParseResult, NodeType

# Regex for EASA article codes (adapted from easa_parser.py)
ARTICLE_CODE_PATTERN = r"[A-Z0-9]+(?:[\.-][A-Z0-9]+)*(?:\([a-z0-9-]+\))*(?:;(?:\([a-z0-9-]+\))*)*"

def parse_easa_html(html_path: Path, regulatory_source: str = "") -> ParseResult:
    """Parse EASA Online Publication HTML file."""
    with open(html_path, "r", encoding="utf-8") as f:
        soup = BeautifulSoup(f, "lxml")

    result = ParseResult(
        source_document_title=regulatory_source or _extract_title(soup),
        source_version=_extract_version(soup),
    )

    # TODO: Implement specific EASA HTML structure parsing logic
    # This will depend on the actual HTML structure of EASA online rules.
    # We'll need to identify:
    # 1. The container for each regulation node (IR, AMC, GM, CS).
    # 2. How to extract the reference code (e.g., "21.A.91").
    # 3. How to extract the content text and HTML.
    # 4. How to build the hierarchy path.

    return result

def _extract_title(soup: BeautifulSoup) -> str:
    title_tag = soup.find("title")
    if title_tag:
        return title_tag.get_text().strip()
    return ""

def _extract_version(soup: BeautifulSoup) -> str | None:
    # Look for "Amendment X", "Issue X", etc. in the page content
    text = soup.get_text()
    m = re.search(r"(Amendment|Issue|Revision)\s+(\d+)", text, re.IGNORECASE)
    if m:
        return f"{m.group(1).capitalize()} {m.group(2)}"
    return None
