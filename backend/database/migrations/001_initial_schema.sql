-- CertifExpert — Phase 1 initial schema
-- Domains: HARVEST (source ingestion), KNOWLEDGE (regulatory graph)
-- EXPERT and ALERTING domains are introduced in later phases.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- HARVEST
-- =============================================================================

CREATE TABLE harvest_sources (
    source_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL UNIQUE,
    base_url      TEXT NOT NULL,
    format        TEXT NOT NULL CHECK (format IN ('HTML', 'PDF', 'MIXED')),
    frequency     TEXT NOT NULL CHECK (frequency IN ('daily', 'weekly', 'monthly', 'manual')),
    last_sync_at  TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE harvest_documents (
    doc_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id     UUID NOT NULL REFERENCES harvest_sources(source_id) ON DELETE CASCADE,
    external_id   TEXT NOT NULL,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    content_hash  TEXT NOT NULL,
    raw_path      TEXT,
    UNIQUE (source_id, external_id)
);

CREATE INDEX idx_harvest_documents_source ON harvest_documents (source_id);

CREATE TABLE harvest_document_versions (
    version_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id        UUID NOT NULL REFERENCES harvest_documents(doc_id) ON DELETE CASCADE,
    version_num   INTEGER NOT NULL,
    content_hash  TEXT NOT NULL,
    captured_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (doc_id, version_num)
);

-- =============================================================================
-- KNOWLEDGE
-- =============================================================================

CREATE TYPE node_type AS ENUM ('IR', 'AMC', 'GM', 'CS');

CREATE TABLE regulatory_nodes (
    node_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_type       node_type NOT NULL,
    reference_code  TEXT NOT NULL,
    title           TEXT,
    content_text    TEXT NOT NULL,
    content_hash    TEXT NOT NULL,
    hierarchy_path  TEXT NOT NULL,
    source_doc_id   UUID REFERENCES harvest_documents(doc_id) ON DELETE SET NULL,
    confidence      NUMERIC(3, 2) NOT NULL DEFAULT 1.00 CHECK (confidence BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (node_type, reference_code)
);

CREATE INDEX idx_nodes_reference    ON regulatory_nodes (reference_code);
CREATE INDEX idx_nodes_hierarchy    ON regulatory_nodes (hierarchy_path);
CREATE INDEX idx_nodes_content_trgm ON regulatory_nodes USING GIN (content_text gin_trgm_ops);

CREATE TYPE edge_type AS ENUM (
    'IMPLEMENTS',
    'ACCEPTABLE_MEANS',
    'GUIDANCE_FOR',
    'REFERENCES',
    'REQUIRES',
    'EQUIVALENT_TO',
    'SUPERSEDES',
    'IF_MINOR',
    'IF_MAJOR',
    'LEADS_TO'
);

CREATE TABLE regulatory_edges (
    edge_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_node_id  UUID NOT NULL REFERENCES regulatory_nodes(node_id) ON DELETE CASCADE,
    target_node_id  UUID NOT NULL REFERENCES regulatory_nodes(node_id) ON DELETE CASCADE,
    relation        edge_type NOT NULL,
    confidence      NUMERIC(3, 2) NOT NULL DEFAULT 1.00 CHECK (confidence BETWEEN 0 AND 1),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_node_id, target_node_id, relation),
    CHECK (source_node_id <> target_node_id)
);

CREATE INDEX idx_edges_source ON regulatory_edges (source_node_id);
CREATE INDEX idx_edges_target ON regulatory_edges (target_node_id);

CREATE TABLE regulatory_changes (
    change_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         UUID NOT NULL REFERENCES regulatory_nodes(node_id) ON DELETE CASCADE,
    change_type     TEXT NOT NULL CHECK (change_type IN ('ADDED', 'MODIFIED', 'DELETED')),
    old_hash        TEXT,
    new_hash        TEXT,
    diff_text       TEXT,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_significant  BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX idx_changes_node ON regulatory_changes (node_id);
