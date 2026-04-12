-- Add UNIQUE constraint on external_id to prevent duplicate sources on re-ingest.
-- PostgreSQL treats multiple NULLs as distinct, so nullable columns are safe with UNIQUE.
ALTER TABLE harvest_sources
    ADD CONSTRAINT harvest_sources_external_id_key UNIQUE (external_id);
