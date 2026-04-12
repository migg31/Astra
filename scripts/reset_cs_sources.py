"""Reset CS-25 and CS-ACNS sources by deleting all their nodes.

This is cleaner than trying to identify duplicates.
After running this, re-run the ingest to get clean data.
"""
import psycopg2
from backend.config import settings

def reset_cs_sources():
    """Delete all CS-25 and CS-ACNS nodes."""
    
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            # Get document IDs for CS-25 and CS-ACNS
            cur.execute("""
                SELECT hd.doc_id, hs.name
                FROM harvest_documents hd
                JOIN harvest_sources hs ON hs.source_id = hd.source_id
                WHERE hs.name LIKE '%CS-25%' OR hs.name LIKE '%CS-ACNS%'
            """)
            
            docs = cur.fetchall()
            print(f"Found {len(docs)} documents to reset:")
            for doc_id, name in docs:
                print(f"  - {name}")
            
            if not docs:
                print("No documents found. Exiting.")
                return
            
            # Delete all nodes for these documents
            doc_ids = [doc_id for doc_id, _ in docs]
            
            print("\nDeleting nodes...")
            # Delete nodes one by one to avoid UUID casting issues
            for doc_id in doc_ids:
                cur.execute("""
                    DELETE FROM regulatory_nodes
                    WHERE source_doc_id = %s
                """, (doc_id,))
            
            deleted_nodes = cur.rowcount
            print(f"  Deleted {deleted_nodes} nodes")
            
            # Delete edges will cascade automatically if FK is set up correctly
            # Otherwise we'd need to delete them first
            
            conn.commit()
            
            print(f"\n✓ Reset complete!")
            print(f"\nNow run:")
            print(f"  python -m backend.harvest.ingest --source cs-25")
            print(f"  python -m backend.harvest.ingest --source cs-acns")


if __name__ == "__main__":
    reset_cs_sources()
