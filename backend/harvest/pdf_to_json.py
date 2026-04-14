"""Standalone CLI: convert a regulatory PDF to Astra JSON format.

Usage:
    python -m backend.harvest.pdf_to_json <pdf_path> [options]

Options:
    --source NAME       Regulatory source name (e.g. "AMC 20-26")
    --type  TYPE        Default node type: AMC | GM | CS | IR  (default: AMC)
    --out   PATH        Output file (default: stdout)

The output JSON can be ingested directly via parse_astra_json(), or edited
manually / processed by an LLM before ingestion.

Output schema:
{
  "title":   str,          // document title
  "version": str | null,   // version label if detected
  "nodes": [
    {
      "type":      str,    // AMC | GM | CS | IR
      "ref":       str,    // unique reference code
      "title":     str,    // section title
      "hierarchy": str,    // "Root / Subpart / Section" path
      "text":      str     // plain-text content
    },
    ...
  ]
}
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def convert(
    pdf_path: Path,
    *,
    regulatory_source: str = "",
    node_type: str = "AMC",
) -> dict:
    """Parse a PDF and return an Astra JSON dict."""
    from backend.harvest.pdf_narrative_parser import parse_narrative_pdf

    result = parse_narrative_pdf(
        pdf_path,
        regulatory_source=regulatory_source,
        node_type=node_type,
    )

    nodes = []
    for node in result.nodes:
        nodes.append({
            "type":      node.node_type,
            "ref":       node.reference_code,
            "title":     node.title,
            "hierarchy": node.hierarchy_path,
            "text":      node.content_text,
        })

    return {
        "title":   result.source_document_title or regulatory_source,
        "version": result.source_version,
        "nodes":   nodes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a regulatory PDF to Astra JSON (for ingestion or LLM post-processing)."
    )
    parser.add_argument("pdf", type=Path, help="Path to the PDF file")
    parser.add_argument("--source", default="", help="Regulatory source name (e.g. 'AMC 20-26')")
    parser.add_argument("--type",   default="AMC", choices=["AMC", "GM", "CS", "IR"],
                        help="Default node type (default: AMC)")
    parser.add_argument("--out", type=Path, default=None, help="Output file path (default: stdout)")
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: {args.pdf} not found", file=sys.stderr)
        sys.exit(1)

    data = convert(args.pdf, regulatory_source=args.source, node_type=args.type)
    output = json.dumps(data, ensure_ascii=False, indent=2)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"Written {len(data['nodes'])} nodes to {args.out}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
