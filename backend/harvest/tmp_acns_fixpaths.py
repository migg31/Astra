"""
Two fixes for CS-ACNS hierarchy_path:
1. PDF nodes with no section (2-level path): inherit hierarchy_path from XML equivalent if exists.
2. Remove orphan nodes with no proper subpart (CERTIFICATION SPECIFICATIONS, GUIDANCE MATERIAL top-level).
"""
import psycopg2
from backend.config import settings

ACNS_SOURCE = "CS-ACNS \u2014 Airborne Communications, Navigation and Surveillance"

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        # 1. For PDF nodes with 2-level path (no section), find XML equivalent and copy its hierarchy_path
        cur.execute("""
            UPDATE regulatory_nodes pdf
            SET hierarchy_path = xml.hierarchy_path
            FROM regulatory_nodes xml
            WHERE pdf.reference_code = xml.reference_code
              AND pdf.node_type = xml.node_type
              AND pdf.hierarchy_path ~ '^CS-ACNS Issue 5 / SUBPART [^/]+$'
              AND xml.hierarchy_path ~ '^CS-ACNS Issue 5 / SUBPART .+ / Section .+'
        """)
        print(f"PDF nodes promoted to XML section path: {cur.rowcount}")

        # 2. Remove top-level orphan nodes (no proper SUBPART)
        cur.execute("""
            SELECT hierarchy_path, COUNT(*) FROM regulatory_nodes
            WHERE hierarchy_path IN (
                'CS-ACNS Issue 5 / GUIDANCE MATERIAL (GM)',
                'CS-ACNS Issue 5 / CERTIFICATION SPECIFICATIONS'
            )
            GROUP BY hierarchy_path
        """)
        print("\nOrphan nodes to reassign:")
        for r in cur.fetchall():
            print(f"  {r[1]}  {r[0]!r}")

        # Reassign GUIDANCE MATERIAL nodes to SUBPART A (general guidance)
        cur.execute("""
            UPDATE regulatory_nodes
            SET hierarchy_path = 'CS-ACNS Issue 5 / SUBPART A \u2014 GENERAL'
            WHERE hierarchy_path = 'CS-ACNS Issue 5 / GUIDANCE MATERIAL (GM)'
        """)
        print(f"Moved GUIDANCE MATERIAL to SUBPART A: {cur.rowcount}")

        cur.execute("""
            UPDATE regulatory_nodes
            SET hierarchy_path = 'CS-ACNS Issue 5 / SUBPART A \u2014 GENERAL'
            WHERE hierarchy_path = 'CS-ACNS Issue 5 / CERTIFICATION SPECIFICATIONS'
        """)
        print(f"Moved CERTIFICATION SPECIFICATIONS to SUBPART A: {cur.rowcount}")

        # Final check
        cur.execute("""
            SELECT SPLIT_PART(hierarchy_path, ' / ', 2) AS lv2,
                   COUNT(*) AS n
            FROM regulatory_nodes
            WHERE hierarchy_path LIKE 'CS-ACNS Issue 5%%'
            GROUP BY lv2 ORDER BY n DESC
        """)
        print("\n=== Final level-2 segments ===")
        for r in cur.fetchall():
            print(f"  {r[1]:5d}  {r[0]!r}")

        # Check remaining 2-level paths in SUBPART B
        cur.execute("""
            SELECT COUNT(*) FROM regulatory_nodes
            WHERE hierarchy_path ~ '^CS-ACNS Issue 5 / SUBPART [^/]+$'
        """)
        print(f"\nRemaining 2-level subpart nodes: {cur.fetchone()[0]}")
    conn.commit()
