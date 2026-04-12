import psycopg2
from backend.config import settings

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'harvest_documents'
            ORDER BY ordinal_position
        """)
        cols = [r[0] for r in cur.fetchall()]
        print("harvest_documents columns:", cols)

        cur.execute("SELECT COUNT(*) FROM harvest_documents")
        print("harvest_documents count:", cur.fetchone()[0])

        cur.execute("SELECT COUNT(*) FROM regulatory_nodes")
        print("regulatory_nodes count:", cur.fetchone()[0])
