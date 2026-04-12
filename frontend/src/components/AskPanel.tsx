import { useState } from "react";
import { askQuestion } from "../api";
import type { AskResponse, SourceNode } from "../types";

interface Props {
  onNavigate: (nodeId: string) => void;
}

export function AskPanel({ onNavigate }: Props) {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState<AskResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await askQuestion({ question: question.trim(), n_sources: 5 });
      setResult(res);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="ask-panel">
      <div className="ask-header">
        <h2>ASK</h2>
        <p className="ask-subtitle">Ask a regulatory question about EASA regulations</p>
      </div>

      <form onSubmit={handleSubmit} className="ask-form">
        <textarea
          className="ask-input"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. When is a design change classified as Major?"
          rows={3}
          disabled={loading}
        />
        <button className="ask-btn" type="submit" disabled={loading || !question.trim()}>
          {loading ? "Searching…" : "Ask"}
        </button>
      </form>

      {error && (
        <div className="ask-error">
          <strong>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div className="ask-result">
          <div className="ask-answer">
            {result.answer.split("\n").map((line, i) =>
              line.trim() ? <p key={i}>{line}</p> : <br key={i} />
            )}
          </div>

          <div className="ask-sources">
            <h3>Sources</h3>
            <ul>
              {result.sources.map((s: SourceNode) => (
                <li
                  key={s.node_id}
                  className="ask-source-item"
                  onClick={() => onNavigate(s.node_id)}
                  title={s.hierarchy_path}
                >
                  <span className={`badge badge-${s.node_type}`}>{s.node_type}</span>
                  <span className="ask-source-ref">{s.reference_code}</span>
                  {s.title && <span className="ask-source-title">{s.title}</span>}
                  <span className="ask-source-score">{Math.round(s.score * 100)}%</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {!result && !loading && !error && (
        <div className="ask-empty">
          <p>Answers are generated exclusively from the ingested EASA regulatory texts.</p>
          <p>Click a source to open the article in EXPLORE.</p>
        </div>
      )}
    </div>
  );
}
