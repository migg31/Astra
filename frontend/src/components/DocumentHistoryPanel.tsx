import { useEffect, useState } from "react";
import type { DocumentHistory, DocumentVersion } from "../api";
import { getDocHistory } from "../api";

interface Props {
  sourceKey: string;           // e.g. 'cs-25', 'cs-acns'
  sourceLabel: string;         // display label
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
    <div className="doc-history-panel">
      <div className="doc-history-header">
        <div className="doc-history-title">
          <span className="doc-history-label">{sourceLabel}</span>
        </div>
        <button className="doc-history-close" onClick={onClose} title="Fermer">✕ Fermer</button>
      </div>

      {loading && <div className="doc-history-loading">Chargement…</div>}
      {error && <div className="doc-history-error">{error}</div>}

      {history && (
        <div className="doc-history-timeline">
          {history.versions.map((v, i) => (
            <TimelineEntry
              key={v.version_id}
              version={v}
              isFirst={i === 0}
              isLast={i === history.versions.length - 1}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function TimelineEntry({
  version,
  isFirst,
  isLast,
}: {
  version: DocumentVersion;
  isFirst: boolean;
  isLast: boolean;
}) {
  if (version.is_indexed) {
    return (
      <div className="timeline-entry timeline-entry--indexed">
        {/* Vertical line above */}
        {!isFirst && <div className="timeline-line timeline-line--dashed" />}
        <div className="timeline-indexed-card">
          <div className="timeline-indexed-badge">
            <span className="timeline-indexed-icon">🗂</span>
            <span className="timeline-indexed-tag">Version indexée</span>
            {version.is_latest_pdf && (
              <span className="timeline-pill timeline-pill--latest">LATEST</span>
            )}
            {!version.is_latest_pdf && (
              <span className="timeline-pill timeline-pill--warn">⚠ Pas la dernière version</span>
            )}
          </div>
          <div className="timeline-indexed-info">
            <strong>{version.version_label}</strong>
            <span className="timeline-indexed-type">
              {version.doc_type === "xml" ? "XML (Easy Access)" : "PDF"}
            </span>
            {version.node_count != null && (
              <span className="timeline-indexed-nodes">{version.node_count} nodes</span>
            )}
            {version.pdf_url && (
              <a
                className="timeline-pdf-link"
                href={version.pdf_url}
                target="_blank"
                rel="noopener noreferrer"
                title="Télécharger le PDF de référence"
              >
                📄 PDF
              </a>
            )}
          </div>
          <div className="timeline-indexed-date">{formatDate(version.pub_date)}</div>
        </div>
        {!isLast && <div className="timeline-line" />}
      </div>
    );
  }

  return (
    <div className="timeline-entry">
      {!isFirst && <div className="timeline-line" />}
      <div className="timeline-dot-row">
        <div className="timeline-dot" />
        <div className="timeline-entry-content">
          <span className="timeline-version-label">{version.version_label}</span>
          <span className="timeline-version-date">{formatDate(version.pub_date)}</span>
          <a
            className="timeline-pdf-link"
            href={version.url}
            target="_blank"
            rel="noopener noreferrer"
            title="Ouvrir sur EASA"
          >
            {version.is_latest_pdf ? "📄 PDF latest" : "📄 PDF"}
          </a>
        </div>
      </div>
      {!isLast && <div className="timeline-line" />}
    </div>
  );
}
