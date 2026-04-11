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

export interface SystemStats {
  nodes_count: number;
  edges_count: number;
  documents_count: number;
  embeddings_count: number;
  db_size_mb: number;
  vector_size_mb: number;
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
