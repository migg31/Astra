import type {
  AskRequest,
  AskResponse,
  GraphData,
  HealthStatus,
  IngestionStatus,
  NeighborsResponse,
  NodeDetail,
  NodeListResponse,
  RegulatorySource,
  SystemConfig,
  SystemStats,
} from "./types";

const API_BASE = "http://localhost:8000";

async function fetchJSON<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`${res.status} ${res.statusText} on ${path}`);
  }
  return res.json() as Promise<T>;
}

export interface CatalogEntry {
  id: string;
  name: string;
  short: string;
  category: string;
  domain: string;
  description: string;
  easa_url: string;
  harvest_key: string | null;
  harvest_source_id: string | null;
  is_active: boolean;
  harvester_enabled: boolean;
  indexed: boolean;
  source_title: string | null;
  source_root: string | null;
  version_label: string | null;
  pub_date: string | null;
  amended_by: string | null;
  node_count: number;
}

export interface CatalogMeta {
  categories: { id: string; label: string }[];
  domains:    { id: string; label: string }[];
}

export function getCatalog(): Promise<CatalogEntry[]> {
  return fetchJSON<CatalogEntry[]>("/api/admin/catalog");
}

export function getCatalogMeta(): Promise<CatalogMeta> {
  return fetchJSON<CatalogMeta>("/api/admin/catalog/meta");
}

export async function patchHarvesterEnabled(sourceId: string, enabled: boolean): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/api/admin/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
  return { ok: true };
}

export async function patchCatalogEntry(
  id: string,
  body: Partial<Pick<CatalogEntry, "category" | "domain" | "is_active" | "description" | "name" | "short" | "easa_url" | "harvest_key">>
): Promise<{ ok: boolean }> {
  const res = await fetch(`${API_BASE}/api/admin/catalog/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json();
}

export function listAllNodes(): Promise<NodeListResponse> {
  return fetchJSON<NodeListResponse>("/api/nodes?limit=20000");
}

export function getNode(nodeId: string): Promise<NodeDetail> {
  return fetchJSON<NodeDetail>(`/api/nodes/${nodeId}`);
}

export function getNeighbors(nodeId: string): Promise<NeighborsResponse> {
  return fetchJSON<NeighborsResponse>(`/api/nodes/${nodeId}/neighbors`);
}

export async function askQuestion(req: AskRequest): Promise<AskResponse> {
  const res = await fetch(`${API_BASE}/api/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<AskResponse>;
}

export function getGraph(): Promise<GraphData> {
  return fetchJSON<GraphData>("/api/graph");
}

// History API
export interface DiffOp {
  op: "equal" | "insert" | "delete";
  text: string;
}

export interface NodeVersion {
  version_id: string;
  version_label: string;
  change_type: "added" | "modified" | "deleted" | "unchanged";
  content_hash: string;
  fetched_at: string;
  diff_prev: DiffOp[] | null;
}

export interface NodeHistoryResponse {
  node_id: string;
  versions: NodeVersion[];
}

export function getNodeHistory(nodeId: string): Promise<NodeHistoryResponse> {
  return fetchJSON<NodeHistoryResponse>(`/api/history/nodes/${nodeId}`);
}

export interface VersionCheckResult {
  source_root: string;
  source_title: string;
  easa_url: string;
  indexed_version: string | null;
  latest_version: string | null;
  is_outdated: boolean;
  checked_at: string;
}

export function getVersionCheck(): Promise<VersionCheckResult[]> {
  return fetchJSON<VersionCheckResult[]>("/api/history/version-check");
}

// Document version history API
export interface DocumentVersion {
  version_id: string;
  source_key: string;
  source_label: string;
  version_label: string;
  pub_date: string | null;
  url: string;
  doc_type: "xml" | "pdf";
  is_indexed: boolean;
  is_latest_pdf: boolean;
  xml_doc_id: string | null;
  node_count: number | null;
  pdf_url: string | null;
}

export interface DocumentHistory {
  source_key: string;
  source_label: string;
  versions: DocumentVersion[];
  indexed_version: DocumentVersion | null;
}

export function getDocHistory(sourceKey: string): Promise<DocumentHistory> {
  return fetchJSON<DocumentHistory>(`/api/doc-history/${sourceKey}`);
}

export function getAllDocHistories(): Promise<DocumentHistory[]> {
  return fetchJSON<DocumentHistory[]>("/api/doc-history");
}

// Admin API
export function getStats(): Promise<SystemStats> {
  return fetchJSON<SystemStats>("/api/admin/stats");
}

export function getHealth(): Promise<HealthStatus> {
  return fetchJSON<HealthStatus>("/api/admin/health");
}

export function getHarvesterStatus(): Promise<IngestionStatus> {
  return fetchJSON<IngestionStatus>("/api/admin/harvester/status");
}

export function listHarvesterSources(): Promise<{ id: string; name: string; external_id: string; enabled: boolean }[]> {
  return fetchJSON("/api/admin/harvester/sources");
}

// Regulatory Sources CRUD
export function listSources(): Promise<RegulatorySource[]> {
  return fetchJSON<RegulatorySource[]>("/api/admin/sources");
}

export async function createSource(body: Omit<RegulatorySource, "source_id" | "last_sync_at">): Promise<RegulatorySource> {
  const res = await fetch(`${API_BASE}/api/admin/sources`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json();
}

export async function updateSource(
  sourceId: string,
  body: { name?: string; base_url?: string; urls?: RegulatorySource["urls"]; enabled?: boolean }
): Promise<RegulatorySource> {
  const res = await fetch(`${API_BASE}/api/admin/sources/${sourceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json();
}

export async function deleteSource(sourceId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/admin/sources/${sourceId}`, { method: "DELETE" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
}

export function getSystemConfig(): Promise<SystemConfig> {
  return fetchJSON<SystemConfig>("/api/admin/config");
}

export async function runEmbeddings(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/admin/embeddings/run`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status}`);
  }
  return res.json();
}

export async function startHarvester(sources: string | string[], reindexVectors = false): Promise<{ message: string }> {
  const sourceList = Array.isArray(sources) ? sources : [sources];
  const res = await fetch(`${API_BASE}/api/admin/harvester/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sources: sourceList, reindex_vectors: reindexVectors }),
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<{ message: string }>;
}
