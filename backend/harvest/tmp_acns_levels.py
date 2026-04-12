import psycopg2
from backend.config import settings

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT
                SPLIT_PART(hierarchy_path, ' / ', 2) AS lv2,
                SPLIT_PART(hierarchy_path, ' / ', 3) AS lv3,
                SPLIT_PART(hierarchy_path, ' / ', 4) AS lv4,
                COUNT(*) AS n
            FROM regulatory_nodes
            WHERE hierarchy_path LIKE 'CS-ACNS Issue 5 / SUBPART B%%'
            GROUP BY lv2, lv3, lv4
            ORDER BY lv2, lv3, n DESC
            LIMIT 20
        """)
        print("=== SUBPART B levels ===")
        for r in cur.fetchall():
            print(f"  lv2={r[0]!r:40s}  lv3={r[1]!r:40s}  lv4={r[2]!r:30s}  n={r[3]}")

        cur.execute("""
            SELECT DISTINCT hierarchy_path
            FROM regulatory_nodes
            WHERE hierarchy_path LIKE 'CS-ACNS Issue 5 / GUIDANCE MATERIAL%%'
               OR hierarchy_path LIKE 'CS-ACNS Issue 5 / CERTIFICATION%%'
            LIMIT 5
        """)
        print("\n=== Orphan top-level nodes ===")
        for r in cur.fetchall():
            print(f"  {r[0]!r}")
