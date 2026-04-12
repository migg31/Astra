-- Migration 007: Add pub_date and amended_by to harvest_documents
-- pub_date: most recent entry-into-force date for the document
-- amended_by: amendment/revision label (e.g. "Amendment 27")

ALTER TABLE harvest_documents
    ADD COLUMN IF NOT EXISTS pub_date   date,
    ADD COLUMN IF NOT EXISTS amended_by text;
