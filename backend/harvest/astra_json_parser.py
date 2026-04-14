"""Parse an Astra JSON file (produced by pdf_to_json.py or an LLM) into a ParseResult.

Astra JSON schema:
{
  "title":   str,
  "version": str | null,
  "nodes": [
    {
      "type":      "AMC" | "GM" | "CS" | "IR",
      "ref":       str,
      "title":     str,
      "hierarchy": str,
      "text":      str,
      "html":      str | null   // optional pre-rendered HTML
    }
  ]
}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from backend.harvest.models import ParsedEdge, ParsedNode, ParseResult


def parse_astra_json(path: Path) -> ParseResult:
    """Load an Astra JSON file and return a ParseResult ready for ingestion."""
    raw = json.loads(path.read_text(encoding="utf-8"))

    result = ParseResult(
        source_document_title=raw.get("title", ""),
        source_version=raw.get("version"),
    )

    for item in raw.get("nodes", []):
        text = item.get("text", "")
        node = ParsedNode(
            node_type=item["type"],
            reference_code=item["ref"],
            title=item.get("title", ""),
            content_text=text,
            content_html=item.get("html"),
            content_hash=hashlib.sha256(text.encode()).hexdigest()[:16],
            hierarchy_path=item.get("hierarchy", ""),
            regulatory_source=item.get("source"),
        )
        result.nodes.append(node)

    for rel in raw.get("relations", []):
        if rel.get("from") and rel.get("to"):
            result.edges.append(ParsedEdge(
                source_ref=rel["from"],
                target_ref=rel["to"],
                relation=rel.get("label", "REFERENCES").upper().replace(" ", "_"),
                confidence=float(rel.get("confidence", 0.8)),
                notes="llm-extracted",
            ))

    return result
