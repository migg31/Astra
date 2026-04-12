export type NodeType = "IR" | "AMC" | "GM" | "CS" | "GROUP";

export interface NodeSummary {
  node_id: string;
  node_type: NodeType;
  reference_code: string;
  title: string | null;
  hierarchy_path: string;
  regulatory_source: string | null;
}

export interface NodeDetail extends NodeSummary {
  content_text: string;
  content_html: string | null;
  content_hash: string;
  regulatory_source: string | null;
  applicability_date: string | null;
  entry_into_force_date: string | null;
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

export interface AskRequest {
  question: string;
  n_sources?: number;
  source_filter?: string | null;
}

export interface SourceNode {
  node_id: string;
  reference_code: string;
  title: string;
  node_type: NodeType;
  hierarchy_path: string;
  score: number;
}

export interface AskResponse {
  answer: string;
  sources: SourceNode[];
  question: string;
}

export interface NeighborsResponse {
  node: NodeSummary;
  outgoing: EdgeOut[];
  incoming: EdgeOut[];
}

// --- Graph / MAP view types ---

export interface GraphNode {
  node_id: string;
  node_type: NodeType;
  reference_code: string;
  title: string | null;
  hierarchy_path: string;
  // D3 simulation fields (mutated at runtime)
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
  fx?: number | null;
  fy?: number | null;
}

export interface GraphEdge {
  edge_id: string;
  source_node_id: string;
  target_node_id: string;
  relation: string;
  confidence: number;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface DocumentInfo {
  source: string;    // regulatory_source value — used as unique ID
  label: string;     // short display name, e.g. "Part 21"
  nodeCount: number;
}

export interface SystemStats {
  nodes_count: number;
  edges_count: number;
  documents_count: number;
  embeddings_count: number;
  db_size_mb: number;
  vector_size_mb: number;
  version_snapshots_count: number;
  harvest_runs_count: number;
  last_harvest_at: string | null;
}

export interface HealthStatus {
  postgres: boolean;
  chroma: boolean;
  ollama_server: boolean;
  ollama_model_embed: boolean;
  ollama_model_chat: boolean;
}

export interface IngestionStatus {
  is_running: boolean;
  last_run_at: string | null;
  last_report: any | null;
  error: string | null;
  log_lines: string[];
  current_source: string | null;
  queue: string[];
  completed: string[];
  embed_done: number;
  embed_total: number;
}

export interface SystemConfig {
  harvester_source_url: string;
  harvester_name: string;
  harvester_frequency: string;
  harvester_format: string;
  data_directory: string;
  db_host: string;
  ollama_base_url: string;
}

export interface RegulatorySource {
  source_id: string;
  name: string;
  base_url: string;
  external_id: string | null;
  format: string;
  frequency: string;
  enabled: boolean;
  last_sync_at: string | null;
}
