-- Migration 013: Add multi-format URLs to harvest_sources
ALTER TABLE harvest_sources ADD COLUMN urls JSONB;

-- Initialize urls with the current base_url for existing records
UPDATE harvest_sources SET urls = jsonb_build_object('xml', base_url) WHERE base_url IS NOT NULL;
