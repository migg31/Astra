-- 014_doc_catalog.sql
-- DB-driven document catalog replacing catalog.py Python hardcode.
-- doc_categories and doc_domains are reference tables.
-- doc_sources is the single source of truth for all known regulatory documents.

CREATE TABLE IF NOT EXISTS doc_categories (
    id         TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    sort_order INT  NOT NULL DEFAULT 99
);

CREATE TABLE IF NOT EXISTS doc_domains (
    id         TEXT PRIMARY KEY,
    label      TEXT NOT NULL,
    sort_order INT  NOT NULL DEFAULT 99
);

CREATE TABLE IF NOT EXISTS doc_sources (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    short              TEXT NOT NULL,
    category_id        TEXT NOT NULL REFERENCES doc_categories(id),
    domain_id          TEXT NOT NULL REFERENCES doc_domains(id),
    description        TEXT NOT NULL DEFAULT '',
    easa_url           TEXT NOT NULL DEFAULT '',
    harvest_key        TEXT,                        -- external_id in harvest_sources (NULL if not harvestable)
    doc_title_pattern  TEXT,                        -- ILIKE pattern to match harvest_documents.title
    ref_code_pattern   TEXT,                        -- Postgres regex on reference_code for per-Part node counts
    is_active          BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order         INT     NOT NULL DEFAULT 99,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_doc_sources_category ON doc_sources(category_id);
CREATE INDEX IF NOT EXISTS idx_doc_sources_domain   ON doc_sources(domain_id);
CREATE INDEX IF NOT EXISTS idx_doc_sources_harvest_key ON doc_sources(harvest_key);
