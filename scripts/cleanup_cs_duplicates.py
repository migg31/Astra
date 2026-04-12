"""Clean up duplicate CS-25 and CS-ACNS nodes after parser fix.

The parser fix changed:
1. IR → CS for bare codes in CS documents (23 nodes in CS-25)
2. Added variant numbers to reference_code (AMC → AMC2, etc.)

This creates duplicates because the UNIQUE constraint is on (node_type, reference_code).
We need to delete the old nodes and keep only the new corrected ones.
"""
import psycopg2
from backend.config import settings

def cleanup_duplicates():
    """Remove old duplicate nodes from CS-25 and CS-ACNS."""
    
    with psycopg2.connect(settings.database_url_sync) as conn:
        with conn.cursor() as cur:
            # 1. Delete old IR nodes from CS-25 that are now CS
            # These are H25.*, K25.*, M25.*, N25.*, S25.* codes
            print("Deleting old IR nodes from CS-25 (now CS)...")
            cur.execute("""
                DELETE FROM regulatory_nodes
                WHERE node_type = 'IR'
                  AND reference_code ~ '^[HKMNS]25\.'
                  AND hierarchy_path LIKE 'Easy Access Rules for Large Aeroplanes (CS-25)%'
            """)
            deleted_ir = cur.rowcount
            print(f"  Deleted {deleted_ir} old IR nodes")
            
            # 2. Find and delete old AMC/GM nodes without variant numbers
            # that now have variants (e.g., old "AMC 25.101(c)" when "AMC1 25.101(c)" exists)
            print("\nFinding AMC/GM nodes with missing variants...")
            
            # Get all AMC/GM nodes with variants
            cur.execute("""
                SELECT DISTINCT 
                    node_type,
                    regexp_replace(reference_code, '^(AMC|GM)\d+\s+', '\1 ') as base_ref
                FROM regulatory_nodes
                WHERE reference_code ~ '^(AMC|GM)\d+\s+'
                  AND (hierarchy_path LIKE 'Easy Access Rules for Large Aeroplanes (CS-25)%'
                       OR hierarchy_path LIKE 'Easy Access Rules for Airborne Communications%')
            """)
            
            variant_nodes = cur.fetchall()
            print(f"  Found {len(variant_nodes)} nodes with variants")
            
            # For each variant node, check if an old non-variant version exists
            deleted_old_amc = 0
            for node_type, base_ref in variant_nodes:
                # Check if old version exists
                cur.execute("""
                    SELECT node_id, reference_code 
                    FROM regulatory_nodes
                    WHERE node_type = %s
                      AND reference_code = %s
                      AND (hierarchy_path LIKE 'Easy Access Rules for Large Aeroplanes (CS-25)%%'
                           OR hierarchy_path LIKE 'Easy Access Rules for Airborne Communications%%')
                """, (node_type, base_ref))
                
                old_nodes = cur.fetchall()
                if old_nodes:
                    for node_id, ref_code in old_nodes:
                        print(f"    Deleting old {node_type} {ref_code}")
                        cur.execute("DELETE FROM regulatory_nodes WHERE node_id = %s", (node_id,))
                        deleted_old_amc += 1
            
            print(f"  Deleted {deleted_old_amc} old AMC/GM nodes without variants")
            
            conn.commit()
            
            print(f"\n✓ Cleanup complete!")
            print(f"  Total deleted: {deleted_ir + deleted_old_amc} nodes")
            
            # Show final counts
            cur.execute("""
                SELECT 
                    CASE 
                        WHEN hierarchy_path LIKE 'Easy Access Rules for Large Aeroplanes (CS-25)%' THEN 'CS-25'
                        WHEN hierarchy_path LIKE 'Easy Access Rules for Airborne Communications%' THEN 'CS-ACNS'
                        ELSE 'Other'
                    END as source,
                    node_type,
                    COUNT(*) as count
                FROM regulatory_nodes
                WHERE hierarchy_path LIKE 'Easy Access Rules for Large Aeroplanes (CS-25)%'
                   OR hierarchy_path LIKE 'Easy Access Rules for Airborne Communications%'
                GROUP BY source, node_type
                ORDER BY source, node_type
            """)
            
            print("\nFinal node counts:")
            for source, node_type, count in cur.fetchall():
                print(f"  {source:15s} {node_type:5s} {count:4d}")


if __name__ == "__main__":
    cleanup_duplicates()
