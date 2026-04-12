import { useEffect, useState } from "react";
import { getNodeHistory } from "../api";
import type { DiffOp, NodeVersion } from "../api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" })
    + " " + d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" });
}

const CHANGE_META: Record<string, { label: string; bg: string; text: string }> = {
  added:     { label: "Added",    bg: "#dcfce7", text: "#15803d" },
  modified:  { label: "Modified", bg: "#fef9c3", text: "#a16207" },
  deleted:   { label: "Deleted",  bg: "#fee2e2", text: "#dc2626" },
  unchanged: { label: "No change",bg: "#f3f4f6", text: "#6b7280" },
};

function DiffView({ ops }: { ops: DiffOp[] }) {
  return (
    <div className="nh-diff">
      {ops.map((op, i) => {
        if (op.op === "equal") return (
          <span key={i} className="nh-diff-equal">{op.text} </span>
        );
        if (op.op === "insert") return (
          <span key={i} className="nh-diff-insert">{op.text} </span>
        );
        return (
          <span key={i} className="nh-diff-delete">{op.text} </span>
        );
      })}
    </div>
  );
}

interface Props {
  nodeId: string;
  onClose: () => void;
}

export function NodeHistoryPanel({ nodeId, onClose }: Props) {
  const [versions, setVersions] = useState<NodeVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setExpanded(null);
    getNodeHistory(nodeId)
      .then((r) => setVersions(r.versions))
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [nodeId]);

  return (
    <div className="nh-panel">
      <div className="nh-header">
        <span className="nh-title">⏱ Version History</span>
        <button className="nh-close" onClick={onClose} title="Close">✕</button>
      </div>

      {loading && <div className="nh-state">Loading history…</div>}
      {error && <div className="nh-state nh-state--error">{error}</div>}
      {!loading && !error && versions.length === 0 && (
        <div className="nh-state">
          No history recorded yet.<br />
          <span className="nh-state-hint">Versions are captured on the next harvest run.</span>
        </div>
      )}

      {!loading && versions.length > 0 && (
        <ul className="nh-list">
          {versions.map((v, idx) => {
            const meta = CHANGE_META[v.change_type] ?? CHANGE_META.unchanged;
            const isFirst = idx === 0;
            const isOpen = expanded === v.version_id;
            return (
              <li key={v.version_id} className={"nh-item" + (isFirst ? " nh-item--current" : "")}>
                <div className="nh-item-row">
                  <span className="nh-item-dot" style={{ background: isFirst ? "#2563eb" : "#d1d5db" }} />
                  <div className="nh-item-meta">
                    <span className="nh-item-version">{v.version_label}</span>
                    {isFirst && <span className="nh-item-current-badge">current</span>}
                    <span
                      className="nh-item-change"
                      style={{ background: meta.bg, color: meta.text }}
                    >
                      {meta.label}
                    </span>
                  </div>
                  <span className="nh-item-date">{formatDate(v.fetched_at)}</span>
                  {v.diff_prev && (
                    <button
                      className={"nh-item-diff-btn" + (isOpen ? " is-open" : "")}
                      onClick={() => setExpanded(isOpen ? null : v.version_id)}
                    >
                      {isOpen ? "Hide diff" : "View diff"}
                    </button>
                  )}
                </div>
                {isOpen && v.diff_prev && (
                  <DiffView ops={v.diff_prev} />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
