"""LLM post-processor for Astra JSON documents.

Takes a raw Astra JSON (output of pdf_to_json.py) and enriches it with:
  - Semantic node type (definition | requirement | guidance | procedure | table | other)
  - Title fixes (truncated, malformed)
  - Cross-reference relations between nodes

Usage:
    python -m backend.harvest.llm_enrich data/amc20-26.json --out data/amc20-26-enriched.json

The output is a valid Astra JSON with:
  - nodes[].semantic_type   (added)
  - nodes[].title           (potentially fixed)
  - relations[]             (new array of {from, to, label, confidence})
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
from pathlib import Path
from typing import Any

BATCH_SIZE = 8  # nodes per LLM call — keep context manageable


# ── LLM client (OpenAI-compatible) ───────────────────────────────────────────

def _get_client(provider: str | None = None):
    from openai import OpenAI
    from backend.config import settings
    if provider == "groq":
        import os
        return OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=settings.ollama_api_key if "groq" in settings.ollama_base_url else os.environ.get("GROQ_API_KEY", settings.ollama_api_key),
        ), "llama-3.3-70b-versatile"
    return OpenAI(
        base_url=settings.ollama_base_url,
        api_key=settings.ollama_api_key,
    ), settings.ollama_model


def _call_llm(client, model: str, system: str, user: str, *, temperature: float = 0.1) -> str:
    resp = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content or ""


# ── Prompts ───────────────────────────────────────────────────────────────────

_SYSTEM = textwrap.dedent("""\
    You are an aviation regulatory expert assistant.
    You analyse EASA regulatory document nodes (AMC, GM, CS sections).
    You respond ONLY with valid JSON, no prose, no markdown fences.
""")

_USER_TEMPLATE = textwrap.dedent("""\
    Below are {n} regulatory nodes from document "{title}".
    For each node:
    1. Assign a semantic_type from: definition | requirement | guidance | procedure | table | other
    2. Fix the title if it is clearly truncated or malformed (keep original if fine)
    3. Find explicit cross-references in the text to other sections
       (patterns: "section X", "paragraph X.Y", "see X.Y.Z", "as per X", "referred to in X")
       and list them as relations.

    Nodes:
    {nodes_json}

    Respond with this exact JSON structure:
    {{
      "fixes": [
        {{"ref": "...", "semantic_type": "...", "title": "..."}}
      ],
      "relations": [
        {{"from": "...", "to_section": "X.Y", "label": "references", "confidence": 0.9}}
      ]
    }}

    Rules:
    - Every node must appear in "fixes" (even if unchanged).
    - "to_section" is the raw section code found in text (e.g. "4.3", "6.2.1").
    - Only include relations you are confident about (confidence >= 0.7).
    - Do not invent relations not present in the text.
""")


# ── Section code → ref resolver ───────────────────────────────────────────────

def _build_code_index(nodes: list[dict]) -> dict[str, str]:
    """Map bare section code (e.g. '4.3') → full ref (e.g. 'AMC 20-26 § 4.3')."""
    index: dict[str, str] = {}
    for node in nodes:
        ref = node["ref"]
        # Extract bare code after "§ "
        m = re.search(r"§\s*([\d.]+)", ref)
        if m:
            index[m.group(1)] = ref
    return index


def _resolve_to_section(to_section: str, code_index: dict[str, str]) -> str | None:
    return code_index.get(to_section)


# ── JSON extraction helper (handles LLM markdown wrapping) ───────────────────

def _extract_json(text: str) -> dict:
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s*```$", "", text.strip(), flags=re.MULTILINE)
    return json.loads(text.strip())


# ── Main enrichment logic ─────────────────────────────────────────────────────

def enrich(input_path: Path, *, verbose: bool = False, provider: str | None = None) -> dict:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    title = raw.get("title", "")
    nodes: list[dict] = raw.get("nodes", [])

    client, model = _get_client(provider)
    if verbose:
        print(f"  Using model: {model}", file=sys.stderr)
    code_index = _build_code_index(nodes)

    # Index nodes by ref for quick lookup
    node_by_ref: dict[str, dict] = {n["ref"]: n for n in nodes}

    all_relations: list[dict] = []
    total_batches = (len(nodes) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(total_batches):
        batch = nodes[batch_idx * BATCH_SIZE : (batch_idx + 1) * BATCH_SIZE]
        if verbose:
            print(f"  Batch {batch_idx + 1}/{total_batches} ({len(batch)} nodes)...", file=sys.stderr)

        # Build compact node list for prompt (ref, title, first 400 chars of text)
        nodes_for_prompt = [
            {
                "ref":   n["ref"],
                "title": n["title"],
                "text":  n["text"][:400] + ("..." if len(n["text"]) > 400 else ""),
            }
            for n in batch
        ]

        user_prompt = _USER_TEMPLATE.format(
            n=len(batch),
            title=title,
            nodes_json=json.dumps(nodes_for_prompt, ensure_ascii=False, indent=2),
        )

        try:
            raw_response = _call_llm(client, model, _SYSTEM, user_prompt)
            result = _extract_json(raw_response)
        except Exception as e:
            if verbose:
                print(f"  [WARN] Batch {batch_idx + 1} failed: {e}", file=sys.stderr)
            continue

        # Apply fixes
        for fix in result.get("fixes", []):
            ref = fix.get("ref", "")
            if ref in node_by_ref:
                if fix.get("semantic_type"):
                    node_by_ref[ref]["semantic_type"] = fix["semantic_type"]
                if fix.get("title") and fix["title"] != node_by_ref[ref]["title"]:
                    node_by_ref[ref]["title_original"] = node_by_ref[ref]["title"]
                    node_by_ref[ref]["title"] = fix["title"]

        # Collect relations
        for rel in result.get("relations", []):
            from_ref = rel.get("from", "")
            to_section = rel.get("to_section", "")
            to_ref = _resolve_to_section(to_section, code_index)
            if from_ref and to_ref and from_ref != to_ref:
                all_relations.append({
                    "from":       from_ref,
                    "to":         to_ref,
                    "label":      rel.get("label", "references"),
                    "confidence": float(rel.get("confidence", 0.8)),
                })

    # Deduplicate relations
    seen_rels: set[tuple] = set()
    unique_relations = []
    for r in all_relations:
        key = (r["from"], r["to"], r["label"])
        if key not in seen_rels:
            seen_rels.add(key)
            unique_relations.append(r)

    return {
        "title":     raw.get("title"),
        "version":   raw.get("version"),
        "nodes":     nodes,
        "relations": unique_relations,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Enrich an Astra JSON file with LLM-extracted semantic types and relations."
    )
    parser.add_argument("input", type=Path, help="Input Astra JSON file")
    parser.add_argument("--out", type=Path, default=None, help="Output file (default: stdout)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--provider", default=None, choices=["groq", "ollama"],
                        help="LLM provider override (default: from config)")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print(f"Enriching {args.input} ...", file=sys.stderr)

    result = enrich(args.input, verbose=args.verbose, provider=args.provider)

    n_nodes = len(result["nodes"])
    n_rels  = len(result["relations"])
    typed   = sum(1 for n in result["nodes"] if n.get("semantic_type"))

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.out:
        args.out.write_text(output, encoding="utf-8")
        print(f"Written {n_nodes} nodes ({typed} typed), {n_rels} relations → {args.out}", file=sys.stderr)
    else:
        print(output)
        print(f"\n# {n_nodes} nodes ({typed} typed), {n_rels} relations", file=sys.stderr)


if __name__ == "__main__":
    main()
