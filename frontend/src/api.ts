import type {
  NeighborsResponse,
  NodeDetail,
  NodeListResponse,
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
