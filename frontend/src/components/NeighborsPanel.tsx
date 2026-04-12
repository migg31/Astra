import { useState } from "react";
import type { EdgeOut, NeighborsResponse, NodeSummary } from "../types";

interface Props {
  neighbors: NeighborsResponse | null;
  loading: boolean;
  onSelect: (node: NodeSummary) => void;
}

const RELATION_META: Record<string, { label: string; color: string; bg: string }> = {
  IMPLEMENTS:       { label: "Implements",               color: "#1d4ed8", bg: "#dbeafe" },
  ACCEPTABLE_MEANS: { label: "Acceptable Means",          color: "#065f46", bg: "#d1fae5" },
  GUIDANCE_FOR:     { label: "Guidance",                  color: "#92400e", bg: "#fef3c7" },
  REFERENCES:       { label: "References",                color: "#4b5563", bg: "#f3f4f6" },
  REQUIRES:         { label: "Requires",                  color: "#7c2d12", bg: "#ffedd5" },
  EQUIVALENT_TO:    { label: "Equivalent",                color: "#5b21b6", bg: "#ede9fe" },
  SUPERSEDES:       { label: "Supersedes",                color: "#831843", bg: "#fce7f3" },
  IF_MINOR:         { label: "If minor change",           color: "#065f46", bg: "#d1fae5" },
  IF_MAJOR:         { label: "If major change",           color: "#7c2d12", bg: "#ffedd5" },
  LEADS_TO:         { label: "Leads to",                  color: "#0c4a6e", bg: "#e0f2fe" },
};

function metaFor(rel: string) {
  return RELATION_META[rel] ?? { label: rel, color: "#4b5563", bg: "#f3f4f6" };
}

function groupByRelation(edges: EdgeOut[]): Map<string, EdgeOut[]> {
  const map = new Map<string, EdgeOut[]>();
  for (const e of edges) {
    if (!map.has(e.relation)) map.set(e.relation, []);
    map.get(e.relation)!.push(e);
  }
  return map;
}

interface RelGroupProps {
  relation: string;
  edges: EdgeOut[];
  direction: "out" | "in";
  onSelect: (node: NodeSummary) => void;
}

function RelGroup({ relation, edges, direction, onSelect }: RelGroupProps) {
  const [open, setOpen] = useState(true);
  const meta = metaFor(relation);
  return (
    <div className="rp-group">
      <button className="rp-group-header" onClick={() => setOpen(!open)}>
        <span className="rp-group-chevron">{open ? "▼" : "▶"}</span>
        <span
          className="rp-rel-badge"
          style={{ background: meta.bg, color: meta.color }}
        >
          {meta.label}
        </span>
        <span className="rp-dir-icon">{direction === "out" ? "↗" : "↙"}</span>
        <span className="rp-group-count">{edges.length}</span>
      </button>
      {open && (
        <ul className="rp-group-list">
          {edges.map((e) => (
            <li key={e.edge_id} className="rp-item" onClick={() => onSelect(e.other)}>
              <span className={`badge badge-${e.other.node_type}`}>{e.other.node_type}</span>
              <span className="rp-item-ref">{e.other.reference_code}</span>
              {e.other.title && (
                <span className="rp-item-title">{e.other.title}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function NeighborsPanel({ neighbors, loading, onSelect }: Props) {
  if (loading) {
    return <aside className="rp-panel rp-empty"><span>Loading…</span></aside>;
  }
  if (!neighbors) {
    return <aside className="rp-panel rp-empty"><span>Select an article</span></aside>;
  }

  const outgoing = groupByRelation(neighbors.outgoing);
  const incoming = groupByRelation(neighbors.incoming);
  const nothing = outgoing.size === 0 && incoming.size === 0;

  return (
    <aside className="rp-panel">
      <div className="rp-header">
        <span className="rp-title">Links</span>
        <span className="rp-total">
          {neighbors.outgoing.length + neighbors.incoming.length}
        </span>
      </div>
      {nothing ? (
        <p className="rp-none">No linked nodes.</p>
      ) : (
        <div className="rp-scroll">
          {[...outgoing.entries()].map(([rel, edges]) => (
            <RelGroup key={`out-${rel}`} relation={rel} edges={edges} direction="out" onSelect={onSelect} />
          ))}
          {[...incoming.entries()].map(([rel, edges]) => (
            <RelGroup key={`in-${rel}`} relation={rel} edges={edges} direction="in" onSelect={onSelect} />
          ))}
        </div>
      )}
    </aside>
  );
}
