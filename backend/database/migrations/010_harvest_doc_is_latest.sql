-- Migration 010: Mark harvest_documents as latest version or historical
-- is_latest = TRUE  → this doc's nodes are the canonical state in regulatory_nodes
-- is_latest = FALSE → historical version; only written to regulatory_node_versions

ALTER TABLE harvest_documents
    ADD COLUMN IF NOT EXISTS is_latest BOOLEAN NOT NULL DEFAULT FALSE;

-- Existing docs: mark all as non-latest by default (will be set explicitly on re-ingest)
UPDATE harvest_documents SET is_latest = FALSE;
