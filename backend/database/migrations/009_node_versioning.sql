-- Migration 009: Node versioning — historical snapshots per regulatory node
-- Enables change detection, word-level diffs, and version history UI

-- ── Per-node version snapshots ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS regulatory_node_versions (
    version_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id         UUID        NOT NULL REFERENCES regulatory_nodes(node_id) ON DELETE CASCADE,
    version_label   TEXT        NOT NULL,   -- e.g. "Amendment 27"
    content_text    TEXT        NOT NULL,
    content_html    TEXT,
    content_hash    TEXT        NOT NULL,   -- MD5 of content_text
    change_type     TEXT        NOT NULL    -- 'added' | 'modified' | 'deleted' | 'unchanged'
                    CHECK (change_type IN ('added', 'modified', 'deleted', 'unchanged')),
    diff_prev       JSONB,                  -- word-level diff vs previous version (null if added)
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_node_versions_node_id
    ON regulatory_node_versions (node_id, fetched_at DESC);

CREATE INDEX IF NOT EXISTS idx_node_versions_change_type
    ON regulatory_node_versions (change_type, fetched_at DESC);

-- ── Per-document harvest run snapshots ───────────────────────────────────
CREATE TABLE IF NOT EXISTS document_harvest_runs (
    run_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          UUID        NOT NULL REFERENCES harvest_documents(doc_id) ON DELETE CASCADE,
    version_label   TEXT        NOT NULL,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    nodes_added     INT         NOT NULL DEFAULT 0,
    nodes_modified  INT         NOT NULL DEFAULT 0,
    nodes_deleted   INT         NOT NULL DEFAULT 0,
    nodes_unchanged INT         NOT NULL DEFAULT 0,
    nodes_total     INT         NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_doc_harvest_runs_doc_id
    ON document_harvest_runs (doc_id, fetched_at DESC);
