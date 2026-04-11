import type {
  AskRequest,
  AskResponse,
  HealthStatus,
  IngestionStatus,
  NeighborsResponse,
  NodeDetail,
  NodeListResponse,
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

export function listAllNodes(): Promise<NodeListResponse> {
  return fetchJSON<NodeListResponse>("/api/nodes?limit=500");
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

export function getSystemConfig(): Promise<SystemConfig> {
  return fetchJSON<SystemConfig>("/api/admin/config");
}

export async function startHarvester(): Promise<{ message: string }> {
  const res = await fetch(`${API_BASE}/api/admin/harvester/run`, {
    method: "POST",
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<{ message: string }>;
}
