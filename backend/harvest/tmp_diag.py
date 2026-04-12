import psycopg2
from backend.config import settings

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        # CS-25 Am28 hierarchy_path samples
        cur.execute("""
            SELECT hierarchy_path, reference_code
            FROM regulatory_nodes
            WHERE regulatory_source LIKE 'CS-25%'
              AND source_doc_id = (
                  SELECT doc_id FROM harvest_documents WHERE title = 'CS-25 Amendment 28'
              )
            ORDER BY hierarchy_path
            LIMIT 20
        """)
        print("=== CS-25 Am28 hierarchy_path samples ===")
        for r in cur.fetchall():
            print(f"  path={r[0]!r}  ref={r[1]!r}")

        # Distinct roots for Am28 only
        cur.execute("""
            SELECT SPLIT_PART(hierarchy_path, ' / ', 1) AS root,
                   SPLIT_PART(hierarchy_path, ' / ', 2) AS sub,
                   COUNT(*) AS n
            FROM regulatory_nodes
            WHERE source_doc_id = (
                SELECT doc_id FROM harvest_documents WHERE title = 'CS-25 Amendment 28'
            )
            GROUP BY root, sub ORDER BY n DESC LIMIT 15
        """)
        print("\n=== CS-25 Am28 root/sub ===")
        for r in cur.fetchall():
            print(f"  root={r[0]!r}  sub={r[1]!r}  n={r[2]}")

        # CS-ACNS missing CS nodes
        cur.execute("""
            SELECT node_type, COUNT(*) FROM regulatory_nodes
            WHERE regulatory_source LIKE 'CS-ACNS%'
            GROUP BY node_type ORDER BY node_type
        """)
        print("\n=== CS-ACNS node_type counts ===")
        for r in cur.fetchall():
            print(f"  {r[0]}: {r[1]}")
