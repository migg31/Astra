import psycopg2, re
from backend.config import settings
from backend.harvest.catalog import CATALOG

with psycopg2.connect(settings.database_url_sync) as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT title FROM harvest_documents")
        db_titles = [r[0] for r in cur.fetchall()]

for entry in CATALOG:
    if not entry.doc_title_pattern:
        continue
    pattern = entry.doc_title_pattern.lower()
    regex = re.compile(
        ".*".join(re.escape(p) for p in pattern.split("%") if p),
        re.IGNORECASE,
    )
    matches = [t for t in db_titles if regex.search(t.lower())]
    status = f"MATCH: {matches[0]!r}" if matches else "NO MATCH"
    print(f"  {entry.short:12s} pattern={entry.doc_title_pattern!r:25s} -> {status}")
