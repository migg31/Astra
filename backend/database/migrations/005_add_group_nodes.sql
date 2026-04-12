-- 005_add_group_nodes.sql
-- Adds GROUP nodes (one per subpart) and CONTAINS edges.
-- GROUP nodes are structural — they have no regulatory content but provide
-- hierarchy anchors for the MAP view and tree expand/collapse in EXPLORE.

-- 1. Extend enums
ALTER TYPE node_type ADD VALUE IF NOT EXISTS 'GROUP';
ALTER TYPE edge_type ADD VALUE IF NOT EXISTS 'CONTAINS';

-- Must commit enum changes before using them in DML
COMMIT;
BEGIN;

-- 2. Insert one GROUP node per unique subpart
--    reference_code = "SUBPART B" (extracted via regex from hierarchy_path)
--    title          = full segment e.g. "SUBPART B — TYPE-CERTIFICATES AND ..."
INSERT INTO regulatory_nodes (
    node_id, node_type, reference_code, title,
    content_text, content_hash, hierarchy_path,
    confidence, created_at, updated_at
)
SELECT DISTINCT
    gen_random_uuid(),
    'GROUP'::node_type,
    substring(split_part(hierarchy_path, ' / ', 3) FROM 'SUBPART\s+[A-Z]') AS reference_code,
    split_part(hierarchy_path, ' / ', 3)                                    AS title,
    ''                                                                       AS content_text,
    md5('')                                                                  AS content_hash,
    split_part(hierarchy_path, ' / ', 1) || ' / ' ||
    split_part(hierarchy_path, ' / ', 2) || ' / ' ||
    split_part(hierarchy_path, ' / ', 3)                                     AS hierarchy_path,
    1.00                                                                     AS confidence,
    NOW()                                                                    AS created_at,
    NOW()                                                                    AS updated_at
FROM regulatory_nodes
WHERE node_type <> 'GROUP'
  AND split_part(hierarchy_path, ' / ', 3) ~* '^SUBPART'
  AND substring(split_part(hierarchy_path, ' / ', 3) FROM 'SUBPART\s+[A-Z]') IS NOT NULL
ON CONFLICT (node_type, reference_code) DO NOTHING;

-- 3. Insert CONTAINS edges: GROUP → every article in that subpart
INSERT INTO regulatory_edges (
    edge_id, source_node_id, target_node_id, relation, confidence, created_at
)
SELECT
    gen_random_uuid(),
    g.node_id   AS source_node_id,
    n.node_id   AS target_node_id,
    'CONTAINS'::edge_type,
    1.00,
    NOW()
FROM regulatory_nodes n
JOIN regulatory_nodes g
    ON  g.node_type = 'GROUP'
    AND split_part(n.hierarchy_path, ' / ', 3) LIKE g.reference_code || '%'
WHERE n.node_type <> 'GROUP'
ON CONFLICT (source_node_id, target_node_id, relation) DO NOTHING;

COMMIT;
