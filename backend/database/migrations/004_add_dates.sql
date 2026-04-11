ALTER TABLE regulatory_nodes
    ADD COLUMN IF NOT EXISTS applicability_date TEXT,
    ADD COLUMN IF NOT EXISTS entry_into_force_date TEXT;
