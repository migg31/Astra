-- Add HTML-rendered content column to regulatory_nodes.
ALTER TABLE regulatory_nodes ADD COLUMN IF NOT EXISTS content_html TEXT;
