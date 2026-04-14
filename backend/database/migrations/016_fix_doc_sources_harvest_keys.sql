-- Migration 016: Fix doc_sources.harvest_key to match actual external_ids in harvest_sources
-- and add missing doc_sources entries for the 12 new XML sources.

-- Fix mismatched harvest_keys (old short keys -> real external_ids)
UPDATE doc_sources SET harvest_key = 'easa-cs23'  WHERE id = 'cs-23';
UPDATE doc_sources SET harvest_key = 'easa-cs27'  WHERE id = 'cs-27';
UPDATE doc_sources SET harvest_key = 'easa-cs29'  WHERE id = 'cs-29';
UPDATE doc_sources SET harvest_key = 'easa-cse'   WHERE id = 'cs-e';
UPDATE doc_sources SET harvest_key = 'easa-cslsa' WHERE id = 'cs-lsa';

-- Add missing catalog entries for new sources
INSERT INTO doc_sources (id, name, short, category_id, domain_id, harvest_key, sort_order)
VALUES
    ('cs-22',   'CS-22 — Sailplanes and Powered Sailplanes', 'CS-22',   'cs',     'initial-airworthiness', 'easa-cs22',    99),
    ('amc-20',  'AMC-20 — Airworthiness AMC',                'AMC-20',  'amcgm',  'initial-airworthiness', 'easa-amc20',   99),
    ('sera',    'SERA — European Rules of the Air',           'SERA',    'ir',     'air-operations',        'easa-sera',    99),
    ('uas',     'UAS — Unmanned Aircraft Systems',            'UAS',     'ir',     'air-operations',        'easa-uas',     99),
    ('atm-ans', 'ATM/ANS Equipment',                          'ATM/ANS', 'ir',     'avionics',              'easa-atm-ans', 99),
    ('infosec', 'Information Security (EU 2023/203)',          'InfoSec', 'ir',     'other',                 'easa-infosec', 99),
    ('gh',      'Ground Handling (EU 2025/23)',                'GH',      'ir',     'other',                 'easa-gh',      99)
ON CONFLICT (id) DO UPDATE SET harvest_key = EXCLUDED.harvest_key;

-- Nullify broken harvest_keys for PDF-only docs (no XML available on EASA)
UPDATE doc_sources SET harvest_key = NULL WHERE id IN ('cs-p', 'cs-apu', 'cs-fcd', 'cs-etso');
