import type { EdgeOut, NeighborsResponse, NodeSummary } from "../types";

interface Props {
  neighbors: NeighborsResponse | null;
  loading: boolean;
  onSelect: (node: NodeSummary) => void;
}

const RELATION_LABELS: Record<string, string> = {
  ACCEPTABLE_MEANS: "Acceptable Means of Compliance",
  GUIDANCE_FOR: "Guidance Material",
  REFERENCES: "References",
  REQUIRES: "Requires",
  IMPLEMENTS: "Implements",
  EQUIVALENT_TO: "Equivalent to",
  SUPERSEDES: "Supersedes",
  IF_MINOR: "If minor",
  IF_MAJOR: "If major",
  LEADS_TO: "Leads to",
};

function labelFor(relation: string): string {
  return RELATION_LABELS[relation] ?? relation;
}

function groupByRelation(edges: EdgeOut[]): Map<string, EdgeOut[]> {
  const map = new Map<string, EdgeOut[]>();
  for (const e of edges) {
    if (!map.has(e.relation)) map.set(e.relation, []);
    map.get(e.relation)!.push(e);
  }
  return map;
}

export function NeighborsPanel({ neighbors, loading, onSelect }: Props) {
  if (loading) {
    return <aside className="neighbors-panel neighbors-empty">Loading…</aside>;
  }
  if (!neighbors) {
    return <aside className="neighbors-panel neighbors-empty">—</aside>;
  }

  const outgoing = groupByRelation(neighbors.outgoing);
  const incoming = groupByRelation(neighbors.incoming);
  const nothing = outgoing.size === 0 && incoming.size === 0;

  return (
    <aside className="neighbors-panel">
      <h2>Related</h2>
      {nothing && <p className="neighbors-empty-msg">No related nodes.</p>}

      {outgoing.size > 0 && (
        <section>
          <h3>Out</h3>
          {[...outgoing.entries()].map(([rel, edges]) => (
            <div key={rel} className="relation-group">
              <h4>{labelFor(rel)}</h4>
              <ul>
                {edges.map((e) => (
                  <li key={e.edge_id} onClick={() => onSelect(e.other)}>
                    <span className={`badge badge-${e.other.node_type}`}>
                      {e.other.node_type}
                    </span>
                    <span>{e.other.reference_code}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}

      {incoming.size > 0 && (
        <section>
          <h3>In</h3>
          {[...incoming.entries()].map(([rel, edges]) => (
            <div key={rel} className="relation-group">
              <h4>{labelFor(rel)}</h4>
              <ul>
                {edges.map((e) => (
                  <li key={e.edge_id} onClick={() => onSelect(e.other)}>
                    <span className={`badge badge-${e.other.node_type}`}>
                      {e.other.node_type}
                    </span>
                    <span>{e.other.reference_code}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </section>
      )}
    </aside>
  );
}
