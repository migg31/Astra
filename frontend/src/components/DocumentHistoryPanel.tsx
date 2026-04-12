import { useEffect, useState } from "react";
import type { DocumentHistory, DocumentVersion } from "../api";
import { getDocHistory } from "../api";

interface Props {
  sourceKey: string;
  sourceLabel: string;
  onClose: () => void;
}

function formatDate(d: string | null): string {
  if (!d) return "—";
  return new Date(d).toLocaleDateString("fr-FR", { year: "numeric", month: "short" });
}

export function DocumentHistoryPanel({ sourceKey, sourceLabel, onClose }: Props) {
  const [history, setHistory] = useState<DocumentHistory | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getDocHistory(sourceKey)
      .then(setHistory)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, [sourceKey]);

  return (
    <div className="dhl-panel">
      <div className="dhl-header">
        <span className="dhl-title">{sourceLabel}</span>
        <button className="dhl-close" onClick={onClose}>✕ Fermer</button>
      </div>

      {loading && <div className="dhl-state">Chargement…</div>}
      {error   && <div className="dhl-state dhl-state--error">{error}</div>}

      {history && (
        <div className="dhl-list">
          {history.versions.map((v) => (
            <VersionRow key={v.version_id} v={v} />
          ))}
        </div>
      )}
    </div>
  );
}

function VersionRow({ v }: { v: DocumentVersion }) {
  return (
    <div className={`dhl-row${v.is_indexed ? " dhl-row--indexed" : ""}`}>
      {/* Left: indexed chip or empty */}
      <div className="dhl-indexed-col">
        {v.is_indexed && <span className="dhl-indexed-chip">INDEXÉ</span>}
      </div>

      {/* Center: label + badges */}
      <div className="dhl-center">
        <span className="dhl-label">{v.version_label}</span>
        <div className="dhl-badges">
          {v.is_latest_pdf && <span className="dhl-badge dhl-badge--latest">latest</span>}
          {v.is_indexed && <span className="dhl-badge dhl-badge--xml">
            {v.doc_type === "xml" ? "XML" : "PDF"}
          </span>}
          {v.is_indexed && v.node_count != null && (
            <span className="dhl-badge dhl-badge--count">{v.node_count} nodes</span>
          )}
          {v.is_indexed && !v.is_latest_pdf && (
            <span className="dhl-badge dhl-badge--warn">⚠ pas la dernière</span>
          )}
        </div>
      </div>

      {/* Right: date + link */}
      <span className="dhl-date">{formatDate(v.pub_date)}</span>
      <a
        className="dhl-link"
        href={v.pdf_url ?? v.url}
        target="_blank"
        rel="noopener noreferrer"
        title="Ouvrir sur EASA"
      >↗</a>
    </div>
  );
}
