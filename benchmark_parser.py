import time
import os
import json
from pathlib import Path
from pydantic import BaseModel, Field

# Ensure we have access to local .env
from dotenv import load_dotenv
load_dotenv()

# --- 1. Current PyMuPDF implementation ---
def run_pymupdf_baseline(pdf_path: Path):
    print("=== Running PyMuPDF (Current Pipeline) ===")
    from backend.harvest.pdf_cs_parser import parse_cs_pdf
    
    start_time = time.time()
    try:
        result = parse_cs_pdf(pdf_path, regulatory_source="CS-AWO")
        elapsed = time.time() - start_time
        print(f"[PyMuPDF] Extracted {len(result.nodes)} nodes in {elapsed:.2f} seconds.")
        print(f"[PyMuPDF] First 2 nodes:")
        for n in result.nodes[:2]:
            print(f"  - {n.node_type} {n.reference_code}: {n.title} ({len(n.content_text)} chars)")
    except Exception as e:
        print(f"[PyMuPDF] Error: {e}")
        elapsed = time.time() - start_time
    print()

# --- 2. Docling + Ollama (Mistral) JSON Mode ---
def run_docling_ollama(pdf_path: Path):
    print("=== Running Docling + Ollama (Mistral JSON Mode) ===")
    try:
        from docling.document_converter import DocumentConverter
    except ImportError:
        print("[Docling] Docling not installed. Run: uv pip install docling")
        return

    try:
        from openai import OpenAI
    except ImportError:
        print("[Ollama] OpenAI client not installed. Run: uv pip install openai")
        return

    start_time = time.time()
    
    # Step A: Docling extraction
    print("[Docling] Converting PDF to Markdown...")
    converter = DocumentConverter()
    doc_result = converter.convert(str(pdf_path))
    md_content = doc_result.document.export_to_markdown()
    
    docling_elapsed = time.time() - start_time
    print(f"[Docling] Markdown extracted in {docling_elapsed:.2f} seconds. ({len(md_content)} chars)")
    
    # Step B: Ollama Structured Extraction
    print("[Ollama] Sending Markdown to Mistral for JSON structured extraction...")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model_name = os.getenv("OLLAMA_MODEL", "mistral")
    
    client = OpenAI(
        base_url=base_url,
        api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
    )
    
    # Define the JSON schema we want Mistral to output
    system_prompt = """
    You are an expert aviation regulatory data extractor.
    Your task is to parse the following Markdown text extracted from an EASA (European Union Aviation Safety Agency) document.
    Extract a list of regulatory nodes. Each node represents a specific article, acceptable means of compliance (AMC), or guidance material (GM).
    
    The JSON output must strictly follow this schema:
    {
      "nodes": [
        {
          "node_type": "CS" or "AMC" or "GM",
          "reference_code": "e.g., CS AWO.A.ALS.101",
          "title": "The title of the section/article",
          "content": "The full text content of the section, without the heading"
        }
      ]
    }
    
    Respond ONLY with the JSON object, without markdown formatting blocks.
    """

    ollama_start = time.time()
    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Extract the nodes from this markdown:\n\n{md_content}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        ollama_elapsed = time.time() - ollama_start
        result_json = response.choices[0].message.content
        
        try:
            data = json.loads(result_json)
            nodes = data.get("nodes", [])
            print(f"[Ollama] Extracted {len(nodes)} nodes in {ollama_elapsed:.2f} seconds.")
            print(f"[Ollama] First 2 nodes:")
            for n in nodes[:2]:
                print(f"  - {n.get('node_type')} {n.get('reference_code')}: {n.get('title')} ({len(n.get('content', ''))} chars)")
        except json.JSONDecodeError:
            print("[Ollama] Failed to parse JSON response:")
            print(result_json[:200] + "...")
            
    except Exception as e:
        print(f"[Ollama] Error communicating with Ollama: {e}")
        
    total_elapsed = time.time() - start_time
    print(f"\n[Total Pipeline] {total_elapsed:.2f} seconds.")

if __name__ == "__main__":
    pdf_file = Path("sample_benchmark.pdf")
    if not pdf_file.exists():
        print(f"Error: {pdf_file} not found. Please run the generation script first.")
    else:
        run_pymupdf_baseline(pdf_file)
        run_docling_ollama(pdf_file)
