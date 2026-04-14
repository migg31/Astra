-- Add external_id and enabled to harvest_sources for persistent configuration management

ALTER TABLE harvest_sources
    ADD COLUMN IF NOT EXISTS external_id TEXT,
    ADD COLUMN IF NOT EXISTS enabled     BOOLEAN NOT NULL DEFAULT TRUE;

CREATE UNIQUE INDEX IF NOT EXISTS idx_harvest_sources_external_id
    ON harvest_sources (external_id)
    WHERE external_id IS NOT NULL;

-- Seed known EASA sources
INSERT INTO harvest_sources (name, base_url, external_id, format, frequency, enabled) VALUES
    ('EASA Part 21',
     'https://www.easa.europa.eu/en/downloads/136660/en',
     'easa-part21', 'MIXED', 'monthly', TRUE),
    ('Continuing Airworthiness (M, 145, 66)',
     'https://www.easa.europa.eu/en/downloads/136681/en',
     'easa-airworthiness', 'MIXED', 'monthly', FALSE),
    ('Air Operations (ORO, CAT)',
     'https://www.easa.europa.eu/en/downloads/136682/en',
     'easa-ops', 'MIXED', 'monthly', TRUE),
    ('Aircrew (FCL, MED)',
     'https://www.easa.europa.eu/en/downloads/136654/en',
     'easa-aircrew', 'MIXED', 'monthly', FALSE),
    ('CS-25 — Large Aeroplanes',
     'https://www.easa.europa.eu/en/downloads/136662/en',
     'easa-cs25', 'MIXED', 'monthly', TRUE),
    ('CS-ACNS — Airborne Communications, Navigation and Surveillance',
     'https://www.easa.europa.eu/en/downloads/136674/en',
     'easa-csacns', 'MIXED', 'monthly', TRUE),
    ('CS-AWO — All Weather Operations',
     'https://www.easa.europa.eu/document-library/easy-access-rules/online-publications/easy-access-rules-all-weather-operations-cs',
     'cs-awo', 'MIXED', 'monthly', TRUE)
ON CONFLICT (name) DO UPDATE
    SET base_url    = EXCLUDED.base_url,
        external_id = EXCLUDED.external_id,
        enabled     = EXCLUDED.enabled;
