-- Migration 015: Seed correct URLs and config for all harvest_sources
-- This replaces the REGULATORY_SOURCES Python dict in ingest.py.
-- The urls JSONB field is the single source of truth for download URLs.
-- use_smart_parser (bool, default true) and doc_format_hint (text) are optional config keys.

INSERT INTO harvest_sources (external_id, name, base_url, format, frequency, urls)
VALUES
    ('easa-part21',      'EASA Part 21',                                              'https://www.easa.europa.eu/en/downloads/136660/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136660/en"}'),
    ('easa-part26',      'Part 26 — Additional Airworthiness Specifications',         'https://www.easa.europa.eu/en/downloads/136670/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136670/en"}'),
    ('easa-airworthiness','Continuing Airworthiness (M, 145, 66, CAMO)',              'https://www.easa.europa.eu/en/downloads/136699/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136699/en"}'),
    ('easa-ops',         'Air Operations (ORO, CAT)',                                 'https://www.easa.europa.eu/en/downloads/136682/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136682/en"}'),
    ('easa-aircrew',     'Aircrew (FCL, MED)',                                        'https://www.easa.europa.eu/en/downloads/136679/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136679/en"}'),
    ('easa-cs25',        'CS-25 — Large Aeroplanes',                                  'https://www.easa.europa.eu/en/downloads/136662/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136662/en", "use_smart_parser": false}'),
    ('easa-csacns',      'CS-ACNS — Airborne Communications, Navigation and Surveillance', 'https://www.easa.europa.eu/en/downloads/136674/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136674/en", "use_smart_parser": false}'),
    ('cs-awo',           'CS-AWO — All Weather Operations',                           'https://www.easa.europa.eu/en/downloads/136530/en', 'MIXED', 'monthly', '{"pdf": "https://www.easa.europa.eu/en/downloads/136530/en", "use_smart_parser": false}'),
    ('easa-aerodromes',  'Aerodromes (ADR)',                                          'https://www.easa.europa.eu/en/downloads/136677/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136677/en"}'),
    ('easa-cs29',        'CS-29 — Large Rotorcraft',                                  'https://www.easa.europa.eu/en/downloads/143408/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/143408/en"}'),
    ('easa-sera',        'SERA — Standardised European Rules of the Air',             'https://www.easa.europa.eu/en/downloads/136676/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136676/en"}'),
    ('easa-infosec',     'Information Security (EU 2023/203 & 2022/1645)',            'https://www.easa.europa.eu/en/downloads/138790/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/138790/en"}'),
    ('easa-gh',          'Ground Handling (EU 2025/23 & 2025/20)',                    'https://www.easa.europa.eu/en/downloads/142666/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/142666/en"}'),
    ('easa-cs27',        'CS-27 — Small Rotorcraft',                                  'https://www.easa.europa.eu/en/downloads/137636/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/137636/en"}'),
    ('easa-cs23',        'CS-23 — Normal-Category Aeroplanes',                        'https://www.easa.europa.eu/en/downloads/138962/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/138962/en"}'),
    ('easa-cse',         'CS-E — Engines',                                            'https://www.easa.europa.eu/en/downloads/139033/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/139033/en"}'),
    ('easa-uas',         'UAS — Unmanned Aircraft Systems (EU 2019/947)',             'https://www.easa.europa.eu/en/downloads/137111/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/137111/en"}'),
    ('easa-atm-ans',     'ATM/ANS Equipment (EU 2023/1769 & 2023/1768)',             'https://www.easa.europa.eu/en/downloads/140636/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/140636/en"}'),
    ('easa-amc20',       'AMC-20 — Airworthiness Acceptable Means of Compliance',    'https://www.easa.europa.eu/en/downloads/137992/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/137992/en"}'),
    ('easa-cslsa',       'CS-LSA — Light Sport Aeroplanes',                           'https://www.easa.europa.eu/en/downloads/136667/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136667/en"}'),
    ('easa-cs22',        'CS-22 — Sailplanes and Powered Sailplanes',                 'https://www.easa.europa.eu/en/downloads/136661/en', 'MIXED', 'monthly', '{"xml": "https://www.easa.europa.eu/en/downloads/136661/en"}')
ON CONFLICT (external_id) DO UPDATE
    SET name     = EXCLUDED.name,
        base_url = EXCLUDED.base_url,
        urls     = EXCLUDED.urls;
