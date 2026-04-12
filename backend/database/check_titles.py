import psycopg2
from backend.config import settings

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT hd.title, hd.external_id, COUNT(rn.node_id) as nodes
            FROM harvest_documents hd
            LEFT JOIN regulatory_nodes rn ON rn.source_doc_id = hd.doc_id
            GROUP BY hd.title, hd.external_id
            ORDER BY hd.title
        """)
        for r in cur.fetchall():
            print(f"  {r[1]:25s}  nodes={r[2]:5d}  title={r[0]!r}")
