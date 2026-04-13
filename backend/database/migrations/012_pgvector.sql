-- P3.1: Enable pgvector and create the node_embeddings table.
-- Replaces ChromaDB as the vector store for regulatory node chunks.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS node_embeddings (
    chunk_id        TEXT PRIMARY KEY,          -- node_id or node_id__c{n} for sub-chunks
    parent_node_id  TEXT NOT NULL,             -- bare node_id (FK to regulatory_nodes)
    chunk_index     INTEGER NOT NULL DEFAULT 0,
    document        TEXT NOT NULL,             -- breadcrumb + chunk text (fed to embedder)
    embedding       vector(768),               -- nomic-embed-text output dimension
    -- denormalised metadata for fast filtering without joins
    node_type       TEXT,
    reference_code  TEXT,
    title           TEXT,
    hierarchy_path  TEXT,
    content_hash    TEXT,
    source_root     TEXT,
    applicability_date TEXT,
    regulatory_source  TEXT
);

-- HNSW index for approximate nearest-neighbour search (cosine distance)
CREATE INDEX IF NOT EXISTS node_embeddings_embedding_idx
    ON node_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Index for fast source_root filtering
CREATE INDEX IF NOT EXISTS node_embeddings_source_root_idx
    ON node_embeddings (source_root);
