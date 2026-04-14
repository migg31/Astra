-- Migration 017: rename doc_sources → regulations, harvest_sources → source_files
-- Only table renames, no column changes.

ALTER TABLE doc_sources    RENAME TO regulations;
ALTER TABLE harvest_sources RENAME TO source_files;

-- Rename indexes to stay consistent
ALTER INDEX IF EXISTS doc_sources_pkey            RENAME TO regulations_pkey;
ALTER INDEX IF EXISTS harvest_sources_pkey        RENAME TO source_files_pkey;
ALTER INDEX IF EXISTS harvest_sources_external_id_key RENAME TO source_files_external_id_key;
