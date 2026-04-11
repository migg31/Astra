ALTER TABLE regulatory_nodes
    ADD COLUMN IF NOT EXISTS regulatory_source TEXT;
