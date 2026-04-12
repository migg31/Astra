-- Migration 011: Regulatory document version catalog
-- Tracks all known versions of each regulatory document (PDF or XML).
-- Decouples version history from regulatory_nodes (which only holds the indexed/active version).
--
-- is_indexed  = TRUE on the version whose nodes are currently in regulatory_nodes
-- is_latest_pdf = TRUE on the most recent PDF version known
-- doc_type    = 'xml' | 'pdf'
-- A same version_label can have both a PDF and an XML entry (e.g. CS-ACNS Issue 5 exists as both)

CREATE TABLE IF NOT EXISTS regulatory_document_versions (
    version_id     UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_key     TEXT        NOT NULL,            -- e.g. 'cs-25', 'cs-acns'
    source_label   TEXT        NOT NULL,            -- e.g. 'CS-25 — Large Aeroplanes'
    version_label  TEXT        NOT NULL,            -- e.g. 'Amendment 28', 'Issue 5'
    pub_date       DATE,
    url            TEXT        NOT NULL,            -- canonical EASA URL
    file_path      TEXT,                            -- local cache path (nullable)
    content_hash   TEXT,
    doc_type       TEXT        NOT NULL             -- 'xml' | 'pdf'
                   CHECK (doc_type IN ('xml', 'pdf')),
    is_indexed     BOOLEAN     NOT NULL DEFAULT FALSE,   -- nodes in regulatory_nodes
    is_latest_pdf  BOOLEAN     NOT NULL DEFAULT FALSE,   -- most recent PDF available
    xml_doc_id     UUID        REFERENCES harvest_documents(doc_id) ON DELETE SET NULL,
    fetched_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_key, version_label, doc_type)
);

CREATE INDEX IF NOT EXISTS idx_rdv_source_key
    ON regulatory_document_versions (source_key, pub_date DESC);

CREATE INDEX IF NOT EXISTS idx_rdv_is_indexed
    ON regulatory_document_versions (source_key, is_indexed)
    WHERE is_indexed = TRUE;
