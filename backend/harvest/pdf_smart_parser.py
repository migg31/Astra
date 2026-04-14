"""Smart PDF parser for EASA regulatory documents.

This parser uses a two-stage approach:
1.  **Visual Layout Analysis (Docling)**: Converts the PDF into clean, semantically
    rich Markdown, natively ignoring page headers, footers, and preserving tables.
2.  **Structured LLM Extraction (Ollama)**: Uses a local LLM in JSON mode to chunk
    the Markdown and extract the regulatory nodes (CS, AMC, GM) with high accuracy.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field
from openai import OpenAI

from backend.config import settings
from backend.harvest.models import ParsedNode, ParseResult, ParsedEdge

logger = logging.getLogger(__name__)

try:
    import markdown as _markdown_lib
    MARKDOWN_AVAILABLE = True
except ImportError:
    _markdown_lib = None  # type: ignore
    MARKDOWN_AVAILABLE = False

try:
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
    DOCLING_AVAILABLE = True
except ImportError as e:
    logger.error(f"Docling import failed: {e}")
    DOCLING_AVAILABLE = False


# ── Internal Models ──────────────────────────────────────────────────────────

@dataclass
class MarkdownChunk:
    content: str
    hierarchy: str = ""  # e.g. "CS-25 / Subpart B / Flight"


# ── Pydantic Schemas for LLM Output ──────────────────────────────────────────

class ExtractedNode(BaseModel):
    node_type: str = Field(description="Must be exactly one of: 'CS', 'AMC', 'GM', or 'IR'")
    reference_code: str = Field(description="The formal reference code, e.g., 'CS AWO.A.ALS.101', 'AMC1 AWO.101'")
    title: str = Field(description="The title of the article or section, without the reference code itself")
    content: str = Field(description="The full body text of the article/section in Markdown format")


class ExtractedNodesList(BaseModel):
    nodes: list[ExtractedNode] = Field(default_factory=list)


# ── Regex Patterns for Edge Extraction ───────────────────────────────────────

# Matches patterns like CS 25.1309, AMC 20-115, GM 21.A.101, etc.
# Note: This is a simplified version of the logic in easa_parser.py
_REF_PATTERN = re.compile(r"\b((?:CS|AMC|GM|IR)\s+[\w\.\-]+(?:\([^)]*\))*)\b", re.IGNORECASE)


# ── Core Parser ─────────────────────────────────────────────────────────────

def parse_smart_pdf(
    pdf_path: Path,
    regulatory_source: str = "",
    progress_callback: Callable[[str], None] | None = None,
    max_chunks: int | None = None  # Added for testing
) -> ParseResult:
    """Parse a PDF using Docling and an LLM."""
    
    if not DOCLING_AVAILABLE:
        raise ImportError(
            "Docling is not installed. This parser requires the 'docling' package. "
            "Please run: uv pip install docling openai"
        )

    def _log(msg: str):
        if progress_callback:
            progress_callback(f"[SmartParser] {msg}")
        else:
            logger.info(msg)

    # 1. Extraction via Docling
    _log(f"Starting visual layout analysis with Docling for {pdf_path.name}...")
    
    # Configure options to be extremely memory-efficient and stable
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False
    
    # Concurrency and device settings are under accelerator_options
    pipeline_options.accelerator_options.num_threads = 1
    pipeline_options.accelerator_options.device = "cpu"
    
    # Important: do not generate images for pages
    if hasattr(pipeline_options, "generate_page_images"):
        pipeline_options.generate_page_images = False
    
    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    doc_result = converter.convert(str(pdf_path))
    md_content = doc_result.document.export_to_markdown()
    del doc_result
    del converter
    
    _log(f"Docling finished. Extracted {len(md_content)} characters of Markdown.")
    
    # Extract version info if available (heuristics on the first 2000 chars)
    version_label = None
    m_ver = re.search(r"(Amendment|Issue|Revision)\s+(\d+)", md_content[:2000], re.IGNORECASE)
    if m_ver:
        version_label = f"{m_ver.group(1).capitalize()} {m_ver.group(2)}"

    # 2. Chunking the Markdown
    # We chunk by roughly 10,000 characters, trying to split on major headers (## or #)
    # to avoid cutting a regulation in half and confusing the LLM.
    _log("Chunking Markdown for LLM processing...")
    chunks = _chunk_markdown(md_content, target_size=10000)
    
    if max_chunks:
        _log(f"Limiting processing to first {max_chunks} chunks as requested.")
        chunks = chunks[:max_chunks]
        
    _log(f"Processing {len(chunks)} chunks.")

    # 3. LLM Extraction (Ollama)
    _log(f"Initializing LLM client (Base: {settings.ollama_base_url}, Model: {settings.ollama_model})")
    
    client = OpenAI(
        base_url=settings.ollama_base_url,
        api_key=settings.ollama_api_key or "ollama",
    )
    
    system_prompt = """
    You are an expert EASA (European Union Aviation Safety Agency) regulatory data extractor.
    Your task is to parse the following Markdown text, which is an excerpt from a regulatory document.
    
    Identify and extract EVERY regulatory node. A regulatory node is an individual rule, requirement, acceptable means of compliance (AMC), or guidance material (GM).
    
    RULES:
    1. Only extract actual regulatory nodes (articles). Do not extract Table of Contents entries, cover pages, or generic preambles unless they are formally numbered (e.g., "CS AWO.100").
    2. The `node_type` MUST be one of: "CS", "AMC", "GM", or "IR".
    3. The `reference_code` must be precise (e.g., "CS AWO.A.ALS.101(a)", "AMC1 AWO.101"). Do not include the title in the reference code.
    4. The `title` should be the heading of the article (e.g., "Continuous descent final approach").
    5. The `content` must contain the FULL text of the article in Markdown format, preserving lists and tables if any.
    
    The output MUST be a valid JSON object matching this schema exactly:
    {
      "nodes": [
        {
          "node_type": "string",
          "reference_code": "string",
          "title": "string",
          "content": "string"
        }
      ]
    }
    
    If no regulatory nodes are found in the text, return {"nodes": []}.
    Output ONLY the JSON object. No markdown fences.
    """

    all_parsed_nodes: list[ParsedNode] = []
    
    for i, chunk_obj in enumerate(chunks, 1):
        _log(f"Processing chunk {i}/{len(chunks)} ({len(chunk_obj.content)} chars) via LLM...")
        
        try:
            response = client.chat.completions.create(
                model=settings.ollama_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": chunk_obj.content}
                ],
                response_format={"type": "json_object"},
                temperature=0.0  # Deterministic output
            )
            
            result_str = response.choices[0].message.content or "{}"
            
            # Clean up potential markdown fences if the model ignored instructions
            result_str = result_str.strip()
            if result_str.startswith("```json"):
                result_str = result_str[7:]
            if result_str.endswith("```"):
                result_str = result_str[:-3]
                
            data = json.loads(result_str.strip())
            extracted_list = ExtractedNodesList(**data)
            
            # Convert to internal ParsedNode dataclass
            for en in extracted_list.nodes:
                # Ensure type is valid
                ntype = en.node_type.upper()
                if ntype not in ("CS", "AMC", "GM", "IR"):
                    if "AMC" in ntype: ntype = "AMC"
                    elif "GM" in ntype: ntype = "GM"
                    elif "CS" in ntype: ntype = "CS"
                    else: ntype = "IR" # fallback
                    
                # Create stable hash
                content_hash = _hash_text(en.content)
                
                # Convert Markdown to HTML for frontend
                if _markdown_lib is not None:
                    content_html = _markdown_lib.markdown(
                        en.content.strip(),
                        extensions=['tables', 'fenced_code']
                    )
                else:
                    content_html = f"<pre>{en.content.strip()}</pre>"

                node = ParsedNode(
                    node_type=ntype, # type: ignore
                    reference_code=en.reference_code.strip(),
                    title=en.title.strip(),
                    content_text=en.content.strip(),
                    content_html=content_html,
                    content_hash=content_hash,
                    hierarchy_path=chunk_obj.hierarchy,
                    regulatory_source=regulatory_source,
                )
                all_parsed_nodes.append(node)
                
            _log(f"  -> Extracted {len(extracted_list.nodes)} nodes from chunk {i}.")
            
        except Exception as e:
            _log(f"  -> ERROR processing chunk {i}: {e}")
            continue

    _log(f"Extraction complete. Total nodes identified: {len(all_parsed_nodes)}.")

    # 4. Edge Extraction (Regex based for now)
    _log("Extracting cross-reference edges...")
    all_edges = _extract_edges(all_parsed_nodes)
    _log(f"Extracted {len(all_edges)} edges.")

    return ParseResult(
        nodes=all_parsed_nodes,
        edges=all_edges,
        source_document_title=regulatory_source,
        source_version=version_label,
    )


def _chunk_markdown(text: str, target_size: int = 10000) -> list[MarkdownChunk]:
    """Split markdown text into chunks roughly matching target_size,
    preferring to split at top-level headers (## or #).
    Tracks the current hierarchy path.
    """
    lines = text.split("\n")
    chunks: list[MarkdownChunk] = []
    current_chunk_lines: list[str] = []
    current_len = 0
    
    # Hierarchy tracking
    current_h1 = ""
    current_h2 = ""
    
    # Safety limit: if a chunk exceeds this, split regardless of headers
    hard_limit = int(target_size * 1.5)
    
    for line in lines:
        # Hierarchy tracking
        if line.startswith("# "):
            current_h1 = line[2:].strip()
            current_h2 = ""
        elif line.startswith("## "):
            current_h2 = line[3:].strip()
            
        # Check if line is a major header for splitting
        is_split_header = line.startswith("# ") or line.startswith("## ")
        
        # Split conditions:
        # 1. We hit a header AND we've reached the target size
        # 2. We've reached the hard limit (even without a header)
        if (current_len >= target_size and is_split_header) or (current_len >= hard_limit):
            hierarchy = f"{current_h1}"
            if current_h2:
                hierarchy += f" / {current_h2}"
                
            chunks.append(MarkdownChunk(
                content="\n".join(current_chunk_lines),
                hierarchy=hierarchy
            ))
            current_chunk_lines = []
            current_len = 0
            
        current_chunk_lines.append(line)
        current_len += len(line) + 1 # +1 for newline
        
    if current_chunk_lines:
        hierarchy = f"{current_h1}"
        if current_h2:
            hierarchy += f" / {current_h2}"
        chunks.append(MarkdownChunk(
            content="\n".join(current_chunk_lines),
            hierarchy=hierarchy
        ))
        
    return chunks


def _extract_edges(nodes: list[ParsedNode]) -> list[ParsedEdge]:
    """Extract references between nodes using regex."""
    edges: list[ParsedEdge] = []
    node_ids = {n.reference_code for n in nodes}
    
    for node in nodes:
        # Search for references in content
        matches = _REF_PATTERN.findall(node.content_text)
        for match in matches:
            ref_code = match.strip()
            
            # Avoid self-references
            if ref_code == node.reference_code:
                continue
                
            edges.append(ParsedEdge(
                source_ref=node.reference_code,
                target_ref=ref_code,
                relation="REFERS_TO"
            ))
            
    # Deduplicate edges
    unique_edges = {}
    for e in edges:
        unique_edges[(e.source_ref, e.target_ref)] = e
        
    return list(unique_edges.values())

def _hash_text(text: str) -> str:
    h = hashlib.md5() # noqa: S324
    h.update(text.encode("utf-8"))
    return h.hexdigest()
