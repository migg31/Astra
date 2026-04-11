export type NodeType = "IR" | "AMC" | "GM" | "CS";

export interface NodeSummary {
  node_id: string;
  node_type: NodeType;
  reference_code: string;
  title: string | null;
  hierarchy_path: string;
}

export interface NodeDetail extends NodeSummary {
  content_text: string;
  content_html: string | null;
  content_hash: string;
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface NodeListResponse {
  total: number;
  limit: number;
  offset: number;
  items: NodeSummary[];
}

export interface EdgeOut {
  edge_id: string;
  relation: string;
  confidence: number;
  notes: string | null;
  other: NodeSummary;
}

export interface NeighborsResponse {
  node: NodeSummary;
  outgoing: EdgeOut[];
  incoming: EdgeOut[];
}
