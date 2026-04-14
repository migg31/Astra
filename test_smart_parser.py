import sys
import os
from pathlib import Path
import logging

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from backend.harvest.pdf_smart_parser import parse_smart_pdf

# Configure logging to see output
logging.basicConfig(level=logging.INFO, format="%(message)s")

def test_cs_awo_parsing():
    pdf_path = Path("data/raw/easa/2026-04-14/cs-awo/document.pdf")
    
    if not pdf_path.exists():
        print(f"❌ Error: PDF not found at {pdf_path}")
        return

    print("\n" + "="*80)
    print(f"🚀 STARTING SMART PARSER TEST ON: {pdf_path.name}")
    print("="*80)
    
    try:
        result = parse_smart_pdf(
            pdf_path=pdf_path,
            regulatory_source="CS-AWO",
            progress_callback=lambda msg: print(f"  [STEP] {msg}"),
            max_chunks=3  # Limit for fast testing
        )
        
        print("\n" + "="*80)
        print("✅ PARSING COMPLETE")
        print("="*80)
        print(f"  • Source Document : {result.source_document_title}")
        print(f"  • Version Label   : {result.source_version or 'N/A'}")
        print(f"  • Nodes Extracted : {len(result.nodes)}")
        print(f"  • Edges Extracted : {len(result.edges)}")
        print("="*80)
        
        if result.nodes:
            print("\n🔍 SAMPLE NODES (First 5):")
            for i, node in enumerate(result.nodes[:5]):
                print(f"\n  #{i+1} [{node.node_type}] {node.reference_code}")
                print(f"    Title     : {node.title}")
                print(f"    Hierarchy : {node.hierarchy_path or 'Root'}")
                print(f"    Content   : {node.content_text[:120]}...")
                print(f"    HTML Size : {len(node.content_html)} bytes")
                
        if result.edges:
            print("\n🔗 SAMPLE EDGES (First 10):")
            for i, edge in enumerate(result.edges[:10]):
                print(f"    {edge.source_id} ──[ {edge.edge_type} ]──▶ {edge.target_id}")

        print("\n" + "="*80)
        print("✨ TEST FINISHED SUCCESSFULLY")
        print("="*80)

    except Exception as e:
        print(f"\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cs_awo_parsing()
