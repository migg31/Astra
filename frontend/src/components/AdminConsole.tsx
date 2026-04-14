import React, { useEffect, useRef, useState } from "react";
import { LayoutDashboard, FileText, Cpu, GitBranch, ArrowLeft, Loader2 } from "lucide-react";
import {
  createSource, getCatalog, getCatalogMeta, getHarvesterStatus, getHealth, getStats,
  getSystemConfig, getVersionCheck, listHarvesterSources, listSources, patchCatalogEntry, patchHarvesterEnabled,
  runEmbeddings, startHarvester, updateSource,
} from "../api";
import type { CatalogEntry, CatalogMeta, VersionCheckResult } from "../api";
import type { HealthStatus, IngestionStatus, RegulatorySource, SystemConfig, SystemStats } from "../types";

type AdminTab = "overview" | "harvest" | "documents" | "versions";

function EmbedSparkline({ log, total }: { log: string[]; total: number }) {
  const ticks = log
    .filter(l => l.includes("[embed:progress]"))
    .map(l => {
      const m = l.match(/\[embed:progress\]\s+(\d+)\/\d+/);
      return m ? parseInt(m[1], 10) : null;
    })
    .filter((v): v is number => v !== null);

  if (ticks.length === 0 || total === 0) return null;

  const W = 200, H = 24, n = ticks.length;
  const bw = Math.max(2, Math.floor(W / Math.max(n, 1)) - 1);

  return (
    <svg width={W} height={H} style={{ display: "block" }}>
      {ticks.map((v, i) => {
        const h = Math.max(2, Math.round((v / total) * H));
        return (
          <rect
            key={i}
            x={i * (bw + 1)}
            y={H - h}
            width={bw}
            height={h}
            fill={v >= total ? "#16CC7F" : "#2563eb"}
            opacity={0.7 + 0.3 * (i / Math.max(n - 1, 1))}
          />
        );
      })}
    </svg>
  );
}

interface AdminConsoleProps {
  onClose: () => void;
}

export function AdminConsole({ onClose }: AdminConsoleProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [harvester, setHarvester] = useState<IngestionStatus | null>(null);
  const [sources, setSources] = useState<{ id: string; name: string; external_id: string; enabled: boolean }[]>([]);
  const [selectedSources, setSelectedSources] = useState<Set<string>>(new Set());
  const logRef = useRef<HTMLPreElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [regulatorySources, setRegulatorySources] = useState<RegulatorySource[]>([]);
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [versionChecks, setVersionChecks] = useState<VersionCheckResult[] | null>(null);
  const [versionCheckLoading, setVersionCheckLoading] = useState(false);
  const [versionCheckError, setVersionCheckError] = useState<string | null>(null);
  const [catalogEntries, setCatalogEntries] = useState<CatalogEntry[]>([]);
  const [catalogMeta, setCatalogMeta] = useState<CatalogMeta | null>(null);
  const [catalogSaving, setCatalogSaving] = useState<string | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [rowUrls, setRowUrls] = useState<Record<string, { xml: string; html: string; pdf: string }>>({});
  const [rowSharedKey, setRowSharedKey] = useState<Record<string, string>>({});
  const [rowSaving, setRowSaving] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [purgeConfirm, setPurgeConfirm] = useState(false);
  const [purgeRunning, setPurgeRunning] = useState(false);
  const [purgeResult, setPurgeResult] = useState<string | null>(null);

  // Add document form
  const BLANK_DOC = { id: "", name: "", short: "", category_id: "", domain_id: "", easa_url: "", description: "", harvest_key: "", doc_title_pattern: "" };
  const [showAddDoc, setShowAddDoc] = useState(false);
  const [newDoc, setNewDoc] = useState(BLANK_DOC);
  const [addDocSaving, setAddDocSaving] = useState(false);

  // Table filters
  const [filterCat, setFilterCat] = useState<string>("all");
  const [filterDomain, setFilterDomain] = useState<string>("all");
  const [filterNavigate, setFilterNavigate] = useState<string>("all");  // all | active | hidden
  const [filterIndexed, setFilterIndexed] = useState<string>("all");    // all | yes | no
  const [filterHarvest, setFilterHarvest] = useState<string>("all");    // all | enabled | disabled | na
  const [docSearch, setDocSearch] = useState<string>("");

  const refreshData = async (initial = false) => {
    try {
      const [s, h, i, cfg, src, regSrc, cat, meta] = await Promise.all([
        getStats(), getHealth(), getHarvesterStatus(), getSystemConfig(),
        listHarvesterSources(), listSources(), getCatalog(), getCatalogMeta(),
      ]);
      setStats(s); setHealth(h); setHarvester(i); setConfig(cfg);
      setSources(src); setRegulatorySources(regSrc);
      setCatalogEntries(cat); setCatalogMeta(meta);
      setError(null);
    } catch (err: any) { setError(err.message); }
    finally { if (initial) setLoading(false); }
  };

  const handleCatalogPatch = async (id: string, field: string, value: unknown) => {
    setCatalogSaving(id);
    try {
      await patchCatalogEntry(id, { [field]: value } as any);
      setCatalogEntries(prev => prev.map(e => e.id === id ? { ...e, [field]: value } : e));
    } catch (err: any) { setError("Catalog update failed: " + err.message); }
    finally { setCatalogSaving(null); }
  };

  useEffect(() => {
    refreshData(true);
    const iv = setInterval(refreshData, 8000);
    return () => clearInterval(iv);
  }, []);

  const handleVersionCheck = async () => {
    setVersionCheckLoading(true); setVersionCheckError(null);
    try { setVersionChecks(await getVersionCheck()); }
    catch (err: any) { setVersionCheckError(err.message); }
    finally { setVersionCheckLoading(false); }
  };

  const [embedRunning, setEmbedRunning] = useState(false);

  const handleRunEmbeddings = async () => {
    setEmbedRunning(true);
    try { await runEmbeddings(); refreshData(); }
    catch (err: any) { setError("Embed failed: " + err.message); }
    finally { setEmbedRunning(false); }
  };

  const [reindexVectors, setReindexVectors] = useState(false);

  const handleRunHarvester = async () => {
    if (selectedSources.size === 0) { setError("Select at least one source."); return; }
    try { await startHarvester(Array.from(selectedSources), reindexVectors); refreshData(); }
    catch (err: any) { setError("Harvester failed: " + err.message); }
  };

  const toggleSource = (id: string) => {
    setSelectedSources(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  useEffect(() => {
    if (logRef.current) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [harvester?.log_lines]);


  const handleAddDoc = async () => {
    if (!newDoc.id || !newDoc.name || !newDoc.short || !newDoc.category_id || !newDoc.domain_id) {
      setError("ID, Name, Short, Category and Domain are required."); return;
    }
    setAddDocSaving(true);
    try {
      const res = await fetch(`/api/admin/catalog`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newDoc),
      });
      if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error((d as any).detail ?? res.status); }
      setShowAddDoc(false);
      setNewDoc(BLANK_DOC);
      await refreshData();
    } catch (err: any) { setError("Add doc failed: " + err.message); }
    finally { setAddDocSaving(false); }
  };

  const TABS: { id: AdminTab; label: string; icon: React.ReactNode; badge?: number }[] = [
    { id: "overview",  label: "Overview",  icon: <LayoutDashboard size={14} strokeWidth={1.8} /> },
    { id: "documents", label: "Documents", icon: <FileText size={14} strokeWidth={1.8} />, badge: catalogEntries.length || undefined },
    { id: "harvest",   label: "Harvest",   icon: <Cpu size={14} strokeWidth={1.8} />, badge: sources.filter(s => s.enabled).length || undefined },
    { id: "versions",  label: "Versions",  icon: <GitBranch size={14} strokeWidth={1.8} /> },
  ];

  return (
    <div className="admin-page">
      <aside className="admin-sidebar">
        <div className="admin-sidebar-brand">
          <div style={{ fontSize: "1rem", fontWeight: 800, letterSpacing: "0.08em", color: "#fff" }}>ASTRA</div>
          <div style={{ fontSize: "0.65rem", color: "#64748b", letterSpacing: "0.12em", marginTop: 1 }}>ADMIN CONSOLE</div>
        </div>
        <nav className="admin-sidebar-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={"admin-nav-item" + (activeTab === t.id ? " is-active" : "")}
              onClick={() => setActiveTab(t.id)}
            >
              <span className="admin-nav-icon">{t.icon}</span>
              <span style={{ flex: 1 }}>{t.label}</span>
              {t.badge !== undefined && (
                <span className="admin-nav-badge">{t.badge}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          <button className="admin-back-btn" onClick={onClose}>
            <ArrowLeft size={12} strokeWidth={2} style={{ marginRight: 5, verticalAlign: "middle" }} />
            Back to app
          </button>
        </div>
      </aside>

      <main className="admin-main">
        {error && (
          <div className="admin-error-banner">
            {error}
            <button onClick={() => setError(null)}>x</button>
          </div>
        )}

        {activeTab === "overview" && (
          <div className="admin-content">
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1.5rem" }}>
              <h1 className="admin-page-title" style={{ margin: 0 }}>Overview</h1>
              {loading && <Loader2 size={16} className="admin-spinner" strokeWidth={2} />}
            </div>
            <div className="admin-cards-row">
              <BigStatCard value={stats?.nodes_count} label="Regulatory Nodes" color="#222F64" loading={loading} />
              <BigStatCard value={stats?.documents_count} label="Documents" color="#007FC2" loading={loading} />
              <BigStatCard value={stats?.edges_count} label="Relations" color="#16a34a" loading={loading} />
              <div style={{ display: "flex", flexDirection: "column", alignItems: "stretch", gap: "0.4rem", flex: "1 1 0" }}>
                <BigStatCard value={stats?.embeddings_count} label="Chunks (pgvector)" color="#7c3aed" loading={loading} />
                {(embedRunning || harvester?.is_running) && (harvester?.embed_total ?? 0) > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.2rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.65rem", color: "#64748b" }}>
                      <span>Re-indexing…</span>
                      <span>{harvester!.embed_done} / {harvester!.embed_total}</span>
                    </div>
                    <div style={{ background: "#e2e8f0", borderRadius: 4, height: 6, overflow: "hidden" }}>
                      <div style={{
                        background: "#7c3aed",
                        height: 6,
                        borderRadius: 4,
                        width: `${Math.round((harvester!.embed_done / harvester!.embed_total) * 100)}%`,
                        transition: "width 0.5s ease",
                      }} />
                    </div>
                    <div style={{ fontSize: "0.62rem", color: "#a78bfa", textAlign: "right" }}>
                      {Math.round((harvester!.embed_done / harvester!.embed_total) * 100)}%
                    </div>
                  </div>
                ) : (embedRunning || harvester?.is_running) ? (
                  <div style={{ fontSize: "0.68rem", color: "#64748b", padding: "0.3rem 0" }}>Starting…</div>
                ) : (
                  <button
                    className="admin-action-btn"
                    onClick={handleRunEmbeddings}
                    title="Re-generate all embeddings into pgvector"
                    style={{ fontSize: "0.72rem", padding: "0.3rem 0.6rem" }}
                  >
                    ⟳ Re-index
                  </button>
                )}
              </div>
            </div>
            <div className="admin-two-col">
              <div className="admin-card">
                <h2 className="admin-card-title">System Health</h2>
                <div className="admin-health-grid">
                  <HealthRow label="PostgreSQL" ok={health?.postgres} />
                  <HealthRow label="pgVector" ok={health?.pgvector} />
                  <HealthRow label="Ollama Server" ok={health?.ollama_server} error={health?.ollama_server_error} />
                  <HealthRow
                    label={config ? `Chat — ${config.chat_model}` : "Chat Model"}
                    ok={health?.ollama_model_chat}
                    sublabel={config ? config.chat_provider : undefined}
                    error={health?.ollama_model_chat_error}
                  />
                  <HealthRow
                    label={config ? `Embed — ${config.embed_model}` : "Embed Model"}
                    ok={health?.ollama_model_embed}
                    error={health?.ollama_model_embed_error}
                  />
                </div>
              </div>
              <div className="admin-card">
                <h2 className="admin-card-title">Storage</h2>
                <div className="admin-kv-list">
                  <KVRow label="PostgreSQL size" value={stats?.db_size_mb ? stats.db_size_mb + " MB" : "-"} />
                  <KVRow label="Vector index" value={stats?.vector_size_mb ? stats.vector_size_mb + " MB" : "-"} />
                  <KVRow label="Version snapshots" value={stats?.version_snapshots_count ?? "-"} />
                  <KVRow label="Harvest runs" value={stats?.harvest_runs_count ?? "-"} />
                  <KVRow label="Last harvest" value={stats?.last_harvest_at ? new Date(stats.last_harvest_at).toLocaleString("fr-FR") : "Never"} />
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === "harvest" && (
          <div className="admin-content">
            <h1 className="admin-page-title">Knowledge Harvester</h1>
            <p className="admin-page-desc">
              Select one or more sources, then run ingestion. Each source is processed sequentially.
              Version snapshots are recorded automatically for every changed node.
            </p>

            <div style={{ display: "flex", gap: "1.25rem", alignItems: "flex-start", width: "100%" }}>
              {/* Source selector */}
              <div className="admin-card" style={{ flex: "1 1 0", minWidth: 0 }}>
                <h2 className="admin-card-title">Select Sources</h2>
                <div className="admin-source-checklist">
                  {sources.length === 0 && (
                    <p style={{ color: "#9ca3af", fontSize: "0.8rem" }}>No sources configured.</p>
                  )}
                  {sources.map(s => (
                    <label key={s.id} className={"admin-source-check" + (!s.enabled ? " is-disabled" : "") + (selectedSources.has(s.external_id) ? " is-selected" : "")}>
                      <input
                        type="checkbox"
                        checked={selectedSources.has(s.external_id)}
                        onChange={() => toggleSource(s.external_id)}
                        disabled={harvester?.is_running || !s.enabled}
                      />
                      <span className="admin-source-check-name">{s.name}</span>
                      {!s.enabled && <span className="admin-source-check-tag">disabled</span>}
                      {harvester?.is_running && harvester.current_source === s.name && (
                        <span className="admin-source-check-tag admin-source-check-tag--running">running</span>
                      )}
                      {harvester?.completed?.includes(s.name) && (
                        <span className="admin-source-check-tag admin-source-check-tag--done">done</span>
                      )}
                    </label>
                  ))}
                </div>

                <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.75rem" }}>
                  <button className="admin-action-btn" onClick={() => setSelectedSources(new Set(sources.filter(s => s.enabled).map(s => s.external_id)))} disabled={harvester?.is_running}>
                    All
                  </button>
                  <button className="admin-action-btn" onClick={() => setSelectedSources(new Set())} disabled={harvester?.is_running}>
                    None
                  </button>
                </div>

                <div className="admin-status-row" style={{ marginTop: "1rem" }}>
                  <span className="admin-label" style={{ margin: 0 }}>Status</span>
                  {harvester?.is_running
                    ? <span className="admin-badge admin-badge--running">RUNNING</span>
                    : <span className="admin-badge admin-badge--idle">IDLE</span>}
                </div>

                <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", marginTop: "0.75rem", fontSize: "0.78rem", cursor: "pointer", userSelect: "none" }}>
                  <input
                    type="checkbox"
                    checked={reindexVectors}
                    onChange={(e) => setReindexVectors(e.target.checked)}
                    disabled={harvester?.is_running}
                  />
                  Re-index vectors after harvest
                </label>

                <button
                  className={"admin-primary-btn" + (harvester?.is_running ? " is-running" : "")}
                  onClick={handleRunHarvester}
                  disabled={harvester?.is_running || selectedSources.size === 0}
                  style={{ marginTop: "0.5rem" }}
                >
                  {harvester?.is_running
                    ? `Running ${harvester.current_source ?? "..."}` 
                    : `Run ${selectedSources.size > 0 ? "(" + selectedSources.size + ")" : ""} Harvester`}
                </button>

                {/* Progress bar */}
                {harvester?.is_running && (harvester.completed?.length + 1) > 0 && (
                  <div style={{ marginTop: "0.75rem" }}>
                    <div style={{ fontSize: "0.7rem", color: "#64748b", marginBottom: "0.3rem" }}>
                      {harvester.completed?.length ?? 0} / {(harvester.completed?.length ?? 0) + (harvester.queue?.length ?? 0) + 1} sources
                    </div>
                    <div style={{ background: "#e2e8f0", borderRadius: 4, height: 6 }}>
                      <div style={{
                        background: "#007FC2",
                        borderRadius: 4,
                        height: 6,
                        width: `${Math.round(((harvester.completed?.length ?? 0) / Math.max(1, (harvester.completed?.length ?? 0) + (harvester.queue?.length ?? 0) + 1)) * 100)}%`,
                        transition: "width 0.4s",
                      }} />
                    </div>
                  </div>
                )}
              </div>

              {/* Log panel */}
              <div className="admin-card" style={{ flex: "2 1 0", minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.75rem" }}>
                  <h2 className="admin-card-title" style={{ margin: 0, flex: 1 }}>Live Log</h2>
                  {harvester?.last_run_at && !harvester.is_running && (
                    <span style={{ fontSize: "0.7rem", color: "#94a3b8" }}>
                      {new Date(harvester.last_run_at).toLocaleString("fr-FR")}
                    </span>
                  )}
                  <button
                    className="admin-action-btn"
                    title="Copy log to clipboard"
                    onClick={() => {
                      const text = harvester?.log_lines?.join("\n") ?? "";
                      navigator.clipboard.writeText(text);
                    }}
                    disabled={!harvester?.log_lines?.length}
                  >
                    Copy
                  </button>
                  <button
                    className="admin-action-btn admin-action-btn--danger"
                    title="Clear log"
                    onClick={() => setHarvester(h => h ? { ...h, log_lines: [] } : h)}
                    disabled={!harvester?.log_lines?.length}
                  >
                    Clear
                  </button>
                </div>
                <pre className="admin-log admin-log--tall" ref={logRef}>
                  {harvester?.log_lines && harvester.log_lines.length > 0
                    ? harvester.log_lines.join("\n")
                    : harvester?.last_report
                      ? "No log — run a harvest to see verbose output."
                      : "Waiting for harvest run..."}
                </pre>
                {/* Embedding sparkline */}
                {(harvester?.embed_total ?? 0) > 0 && (
                  <div style={{ marginTop: "0.75rem" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: "0.68rem", color: "#64748b", marginBottom: "0.3rem" }}>
                      <span>Embeddings</span>
                      <span>{harvester!.embed_done} / {harvester!.embed_total}</span>
                    </div>
                    {/* Sparkline SVG — 60 × 18 px, one bar per batch tick */}
                    <EmbedSparkline log={harvester!.log_lines} total={harvester!.embed_total} />
                    <div style={{ background: "#e2e8f0", borderRadius: 4, height: 4, marginTop: "0.3rem" }}>
                      <div style={{
                        background: "#16CC7F",
                        borderRadius: 4,
                        height: 4,
                        width: `${harvester!.embed_total > 0 ? Math.round(harvester!.embed_done / harvester!.embed_total * 100) : 0}%`,
                        transition: "width 0.4s",
                      }} />
                    </div>
                  </div>
                )}

                {harvester?.error && (
                  <div style={{ marginTop: "0.5rem", padding: "0.5rem 0.75rem", background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, color: "#b91c1c", fontSize: "0.78rem" }}>
                    {harvester.error}
                  </div>
                )}
              </div>
            </div>

            {/* ── Danger zone ── */}
            <div className="admin-card" style={{ marginTop: "2rem", border: "1px solid #7f1d1d", background: "#1a0a0a" }}>
              <h2 className="admin-card-title" style={{ color: "#fca5a5", margin: "0 0 0.5rem" }}>Danger zone</h2>
              <p style={{ color: "#9ca3af", fontSize: "0.82rem", margin: "0 0 1rem" }}>
                Purge all indexed data — nodes, documents, embeddings and version snapshots.
                <br />
                <strong style={{ color: "#fca5a5" }}>The document catalog and harvest source config are preserved.</strong>
              </p>
              {purgeResult && (
                <div style={{ marginBottom: "0.75rem", padding: "0.5rem 0.75rem", background: "#14532d", border: "1px solid #16a34a", borderRadius: 6, color: "#bbf7d0", fontSize: "0.8rem" }}>
                  ✓ {purgeResult}
                </div>
              )}
              {!purgeConfirm ? (
                <button
                  onClick={() => { setPurgeConfirm(true); setPurgeResult(null); }}
                  disabled={purgeRunning || harvester?.is_running}
                  style={{ background: "#7f1d1d", color: "#fca5a5", border: "1px solid #991b1b", borderRadius: 6, padding: "0.5rem 1.25rem", cursor: "pointer", fontWeight: 600, fontSize: "0.85rem" }}
                >
                  🗑 Purge database
                </button>
              ) : (
                <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                  <span style={{ color: "#fca5a5", fontWeight: 600, fontSize: "0.85rem" }}>⚠ This cannot be undone. Confirm?</span>
                  <button
                    onClick={async () => {
                      setPurgeRunning(true);
                      try {
                        const res = await fetch("/api/admin/purge", { method: "POST" });
                        const data = await res.json();
                        if (!res.ok) throw new Error(data.detail ?? res.status);
                        setPurgeResult(data.message);
                        await refreshData();
                      } catch (err: any) { setError("Purge failed: " + err.message); }
                      finally { setPurgeRunning(false); setPurgeConfirm(false); }
                    }}
                    disabled={purgeRunning}
                    style={{ background: "#dc2626", color: "#fff", border: "none", borderRadius: 6, padding: "0.5rem 1.25rem", cursor: "pointer", fontWeight: 700, fontSize: "0.85rem" }}
                  >
                    {purgeRunning ? "Purging…" : "Yes, purge everything"}
                  </button>
                  <button
                    onClick={() => setPurgeConfirm(false)}
                    style={{ background: "none", color: "#9ca3af", border: "1px solid #374151", borderRadius: 6, padding: "0.5rem 1rem", cursor: "pointer", fontSize: "0.85rem" }}
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "documents" && (
          <div className="admin-content">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
              <div>
                <h1 className="admin-page-title" style={{ margin: 0 }}>Documents</h1>
                <p className="admin-page-desc" style={{ margin: "4px 0 0" }}>
                  {catalogEntries.filter(e => e.indexed).length} / {catalogEntries.length} indexed
                  &nbsp;·&nbsp;{regulatorySources.filter(s => s.enabled).length} harvester sources active
                </p>
              </div>
              <button
                onClick={() => { setShowAddDoc(v => !v); setNewDoc(BLANK_DOC); }}
                className="admin-primary-btn"
                style={{ width: "auto", padding: "0.5rem 1.25rem" }}
              >
                {showAddDoc ? "✕ Cancel" : "+ Add document"}
              </button>
            </div>

            {/* ── Add document form ── */}
            {showAddDoc && (
              <div className="admin-card" style={{ marginBottom: "1rem", padding: "1rem 1.25rem" }}>
                <h3 style={{ margin: "0 0 0.75rem", fontSize: "0.9rem", color: "#e2e8f0" }}>New document</h3>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "10px", marginBottom: "10px" }}>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>ID (slug) *</div>
                    <input value={newDoc.id} onChange={e => setNewDoc(p => ({ ...p, id: e.target.value }))}
                      placeholder="e.g. cs-e" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Short name *</div>
                    <input value={newDoc.short} onChange={e => setNewDoc(p => ({ ...p, short: e.target.value }))}
                      placeholder="e.g. CS-E" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Full name *</div>
                    <input value={newDoc.name} onChange={e => setNewDoc(p => ({ ...p, name: e.target.value }))}
                      placeholder="e.g. CS-E — Engines" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Category *</div>
                    <select value={newDoc.category_id} onChange={e => setNewDoc(p => ({ ...p, category_id: e.target.value }))}
                      style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }}>
                      <option value="">— select —</option>
                      {(catalogMeta?.categories ?? []).map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Domain *</div>
                    <select value={newDoc.domain_id} onChange={e => setNewDoc(p => ({ ...p, domain_id: e.target.value }))}
                      style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }}>
                      <option value="">— select —</option>
                      {(catalogMeta?.domains ?? []).map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
                    </select>
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>EASA URL</div>
                    <input value={newDoc.easa_url} onChange={e => setNewDoc(p => ({ ...p, easa_url: e.target.value }))}
                      placeholder="https://www.easa.europa.eu/..." style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div style={{ gridColumn: "1 / -1" }}>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Description</div>
                    <input value={newDoc.description} onChange={e => setNewDoc(p => ({ ...p, description: e.target.value }))}
                      placeholder="Short description" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Harvest key <span style={{ color: "#475569" }}>(external_id of harvest source)</span></div>
                    <input value={newDoc.harvest_key} onChange={e => setNewDoc(p => ({ ...p, harvest_key: e.target.value }))}
                      placeholder="e.g. easa-cs22" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                  <div>
                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>Doc title pattern <span style={{ color: "#475569" }}>(ILIKE, e.g. %CS-22%)</span></div>
                    <input value={newDoc.doc_title_pattern} onChange={e => setNewDoc(p => ({ ...p, doc_title_pattern: e.target.value }))}
                      placeholder="e.g. %CS-22%" style={{ width: "100%", background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem", boxSizing: "border-box" }} />
                  </div>
                </div>
                <button onClick={handleAddDoc} disabled={addDocSaving} className="admin-action-btn admin-action-btn--save" style={{ padding: "5px 18px" }}>
                  {addDocSaving ? "Saving…" : "Create document"}
                </button>
              </div>
            )}

            {/* ── Filters toolbar ── */}
            <div style={{ display: "flex", gap: "8px", flexWrap: "wrap", alignItems: "center", marginBottom: "0.75rem" }}>
              <input
                value={docSearch} onChange={e => setDocSearch(e.target.value)}
                placeholder="Search…"
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 10px", fontSize: "0.8rem", width: 160 }}
              />
              <select value={filterCat} onChange={e => setFilterCat(e.target.value)}
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem" }}>
                <option value="all">All categories</option>
                {(catalogMeta?.categories ?? []).map(c => <option key={c.id} value={c.id}>{c.label}</option>)}
              </select>
              <select value={filterDomain} onChange={e => setFilterDomain(e.target.value)}
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem" }}>
                <option value="all">All domains</option>
                {(catalogMeta?.domains ?? []).map(d => <option key={d.id} value={d.id}>{d.label}</option>)}
              </select>
              <select value={filterNavigate} onChange={e => setFilterNavigate(e.target.value)}
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem" }}>
                <option value="all">Navigate: all</option>
                <option value="active">Navigate: visible</option>
                <option value="hidden">Navigate: hidden</option>
              </select>
              <select value={filterIndexed} onChange={e => setFilterIndexed(e.target.value)}
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem" }}>
                <option value="all">Indexed: all</option>
                <option value="yes">Indexed: yes</option>
                <option value="no">Indexed: no</option>
              </select>
              <select value={filterHarvest} onChange={e => setFilterHarvest(e.target.value)}
                style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "4px 8px", fontSize: "0.8rem" }}>
                <option value="all">Harvester: all</option>
                <option value="enabled">Harvester: on</option>
                <option value="disabled">Harvester: off</option>
                <option value="na">Harvester: n/a</option>
              </select>
              {(filterCat !== "all" || filterDomain !== "all" || filterNavigate !== "all" || filterIndexed !== "all" || filterHarvest !== "all" || docSearch) && (
                <button onClick={() => { setFilterCat("all"); setFilterDomain("all"); setFilterNavigate("all"); setFilterIndexed("all"); setFilterHarvest("all"); setDocSearch(""); }}
                  style={{ background: "none", border: "1px solid #475569", borderRadius: 4, color: "#94a3b8", cursor: "pointer", padding: "4px 10px", fontSize: "0.78rem" }}>
                  ✕ Clear
                </button>
              )}
            </div>

            <div className="admin-card" style={{ padding: 0, overflow: "auto" }}>
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.82rem" }}>
                <thead>
                  <tr style={{ borderBottom: "2px solid #1e293b", background: "#0f172a", textAlign: "left" }}>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8" }}>Document</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8" }}>Category</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8" }}>Domain</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8", textAlign: "center" }}>Navigate</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8", textAlign: "center" }}>Indexed</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8", textAlign: "center" }}>Harvester</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8" }}>Sources</th>
                    <th style={{ padding: "8px 12px", fontWeight: 600, color: "#94a3b8" }}>Last sync</th>
                    <th style={{ padding: "8px 12px" }}></th>
                  </tr>
                </thead>
                <tbody>
                  {catalogEntries
                    .filter(e => {
                      if (docSearch && !e.short.toLowerCase().includes(docSearch.toLowerCase()) && !e.name.toLowerCase().includes(docSearch.toLowerCase())) return false;
                      if (filterCat !== "all" && e.category !== filterCat) return false;
                      if (filterDomain !== "all" && e.domain !== filterDomain) return false;
                      if (filterNavigate === "active" && !e.is_active) return false;
                      if (filterNavigate === "hidden" && e.is_active) return false;
                      if (filterIndexed === "yes" && !e.indexed) return false;
                      if (filterIndexed === "no" && e.indexed) return false;
                      if (filterHarvest === "enabled" && (!e.harvest_source_id || !e.harvester_enabled)) return false;
                      if (filterHarvest === "disabled" && (!e.harvest_source_id || e.harvester_enabled)) return false;
                      if (filterHarvest === "na" && e.harvest_source_id) return false;
                      return true;
                    })
                    .map((entry) => {
                    const saving = catalogSaving === entry.id;
                    const regSrc = regulatorySources.find(s => s.external_id === entry.harvest_key);
                    return (
                      <React.Fragment key={entry.id}>
                      <tr style={{ borderBottom: "1px solid #1e293b", opacity: saving ? 0.5 : 1, background: entry.is_active ? undefined : "rgba(0,0,0,0.15)" }}>
                        <td style={{ padding: "7px 12px" }}>
                          <div style={{ fontWeight: 600, color: "#e2e8f0" }}>{entry.short}</div>
                          <div style={{ color: "#64748b", fontSize: "0.72rem", marginTop: 2 }}>{entry.name}</div>
                          {entry.node_count > 0 && (
                            <div style={{ color: "#475569", fontSize: "0.72rem" }}>{entry.node_count.toLocaleString()} nodes</div>
                          )}
                        </td>
                        <td style={{ padding: "7px 12px" }}>
                          <select
                            value={entry.category}
                            disabled={saving}
                            onChange={(e) => handleCatalogPatch(entry.id, "category_id", e.target.value)}
                            style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "2px 6px", fontSize: "0.78rem", width: "100%" }}
                          >
                            {(catalogMeta?.categories ?? []).map((c) => (
                              <option key={c.id} value={c.id}>{c.label}</option>
                            ))}
                          </select>
                        </td>
                        <td style={{ padding: "7px 12px" }}>
                          <select
                            value={entry.domain}
                            disabled={saving}
                            onChange={(e) => handleCatalogPatch(entry.id, "domain_id", e.target.value)}
                            style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "2px 6px", fontSize: "0.78rem", width: "100%" }}
                          >
                            {(catalogMeta?.domains ?? []).map((d) => (
                              <option key={d.id} value={d.id}>{d.label}</option>
                            ))}
                          </select>
                        </td>
                        <td style={{ padding: "7px 12px", textAlign: "center" }}>
                          <button
                            onClick={() => handleCatalogPatch(entry.id, "is_active", !entry.is_active)}
                            disabled={saving}
                            className={"admin-toggle" + (entry.is_active ? " is-on" : "")}
                            title={entry.is_active ? "Visible in Navigate" : "Hidden in Navigate"}
                          >
                            <span className="admin-toggle-thumb" />
                          </button>
                        </td>
                        <td style={{ padding: "7px 12px", textAlign: "center" }}>
                          {entry.indexed
                            ? <span style={{ color: "#22c55e", fontWeight: 700 }}>✓</span>
                            : <span style={{ color: "#374151" }}>—</span>}
                        </td>
                        <td style={{ padding: "7px 12px", textAlign: "center" }}>
                          {entry.harvest_source_id ? (
                            <button
                              onClick={async () => {
                                if (!entry.harvest_source_id) return;
                                setCatalogSaving(entry.id);
                                try {
                                  await patchHarvesterEnabled(entry.harvest_source_id, !entry.harvester_enabled);
                                  setCatalogEntries(prev => prev.map(e => e.id === entry.id ? { ...e, harvester_enabled: !e.harvester_enabled } : e));
                                  await refreshData();
                                } catch (err: any) { setError("Harvester toggle failed: " + err.message); }
                                finally { setCatalogSaving(null); }
                              }}
                              disabled={saving}
                              className={"admin-toggle" + (entry.harvester_enabled ? " is-on" : "")}
                              title={entry.harvester_enabled ? "Harvester enabled" : "Harvester disabled"}
                            >
                              <span className="admin-toggle-thumb" />
                            </button>
                          ) : (
                            <span style={{ color: "#374151", fontSize: "0.72rem" }}>n/a</span>
                          )}
                        </td>
                        <td style={{ padding: "7px 12px" }}>
                          {regSrc ? (
                            <div style={{ display: "flex", gap: "6px", fontSize: "0.72rem", flexWrap: "wrap" }}>
                              {regSrc.urls?.xml && <a href={regSrc.urls.xml} target="_blank" rel="noreferrer" className="admin-link">XML</a>}
                              {regSrc.urls?.html && <a href={regSrc.urls.html} target="_blank" rel="noreferrer" className="admin-link">HTML</a>}
                              {regSrc.urls?.pdf && <a href={regSrc.urls.pdf} target="_blank" rel="noreferrer" className="admin-link">PDF</a>}
                              {!regSrc.urls?.xml && !regSrc.urls?.html && !regSrc.urls?.pdf && regSrc.base_url && (
                                <a href={regSrc.base_url} target="_blank" rel="noreferrer" className="admin-link">EASA ↗</a>
                              )}
                            </div>
                          ) : (
                            <span style={{ color: "#374151", fontSize: "0.72rem" }}>—</span>
                          )}
                        </td>
                        <td style={{ padding: "7px 12px", color: "#475569", fontSize: "0.78rem", whiteSpace: "nowrap" }}>
                          {regSrc?.last_sync_at ? new Date(regSrc.last_sync_at).toLocaleDateString("fr-FR") : "—"}
                        </td>
                        <td style={{ padding: "7px 12px", textAlign: "right" }}>
                          <button
                            onClick={() => {
                              const isOpen = expandedRow === entry.id;
                              setExpandedRow(isOpen ? null : entry.id);
                              if (!isOpen && !rowUrls[entry.id]) {
                                setRowUrls(prev => ({ ...prev, [entry.id]: {
                                  xml:  regSrc?.urls?.xml  ?? "",
                                  html: regSrc?.urls?.html ?? "",
                                  pdf:  regSrc?.urls?.pdf  ?? "",
                                }}));
                              }
                            }}
                            style={{ background: "none", border: "1px solid #334155", borderRadius: 4, color: "#94a3b8", cursor: "pointer", padding: "2px 8px", fontSize: "0.75rem" }}
                          >
                            {expandedRow === entry.id ? "▲" : "✎"}
                          </button>
                        </td>
                      </tr>
                      {expandedRow === entry.id && (() => {
                        const urls = rowUrls[entry.id] ?? { xml: "", html: "", pdf: "" };
                        const sharedKey = rowSharedKey[entry.id] ?? "";
                        const usingShare = !entry.harvest_source_id && sharedKey !== "";
                        const docsWithSource = catalogEntries.filter(e => e.harvest_key && e.id !== entry.id);
                        return (
                        <tr key={entry.id + "-expand"}>
                          <td colSpan={9} style={{ padding: "16px 24px", background: "#0c1729", borderBottom: "2px solid #1e293b" }}>
                            {!entry.harvest_source_id && (
                              <p style={{ margin: "0 0 12px", color: "#64748b", fontSize: "0.78rem" }}>
                                Ce document n'a pas encore de source de données configurée.
                              </p>
                            )}
                            <div style={{ display: "flex", gap: "20px", alignItems: "flex-start", flexWrap: "wrap" }}>

                              {/* Option A — URL directe */}
                              <div style={{ flex: "1 1 300px" }}>
                                <div style={{ color: "#94a3b8", fontSize: "0.72rem", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                  {entry.harvest_source_id ? "Mettre à jour les URLs" : "Option A — Nouveau fichier XML / PDF"}
                                </div>
                                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                  <div>
                                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>XML URL</div>
                                    <input
                                      value={urls.xml}
                                      onChange={e => setRowUrls(prev => ({ ...prev, [entry.id]: { ...prev[entry.id], xml: e.target.value } }))}
                                      placeholder="https://easa.europa.eu/en/downloads/XXXXXX/en"
                                      style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "5px 8px", fontSize: "0.8rem", width: "100%", boxSizing: "border-box" }}
                                    />
                                  </div>
                                  <div>
                                    <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 3 }}>PDF URL <span style={{ color: "#475569" }}>(si pas de XML)</span></div>
                                    <input
                                      value={urls.pdf}
                                      onChange={e => setRowUrls(prev => ({ ...prev, [entry.id]: { ...prev[entry.id], pdf: e.target.value } }))}
                                      placeholder="https://easa.europa.eu/en/downloads/XXXXXX/en"
                                      style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "5px 8px", fontSize: "0.8rem", width: "100%", boxSizing: "border-box" }}
                                    />
                                  </div>
                                </div>
                              </div>

                              {/* Option B — Partager source existante (seulement si pas encore de source) */}
                              {!entry.harvest_source_id && docsWithSource.length > 0 && (
                                <div style={{ flex: "1 1 260px" }}>
                                  <div style={{ color: "#94a3b8", fontSize: "0.72rem", fontWeight: 600, marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.06em" }}>
                                    Option B — Partager la source d'un document existant
                                  </div>
                                  <div style={{ color: "#64748b", fontSize: "0.72rem", marginBottom: 4 }}>
                                    Ce doc fait partie du même fichier XML qu'un autre doc déjà configuré
                                  </div>
                                  <select
                                    value={sharedKey}
                                    onChange={e => setRowSharedKey(prev => ({ ...prev, [entry.id]: e.target.value }))}
                                    style={{ background: "#1e293b", color: "#e2e8f0", border: "1px solid #334155", borderRadius: 4, padding: "5px 8px", fontSize: "0.8rem", width: "100%" }}
                                  >
                                    <option value="">— Sélectionner un document —</option>
                                    {docsWithSource.map(d => (
                                      <option key={d.id} value={d.harvest_key!}>
                                        {d.short} ({d.harvest_key})
                                      </option>
                                    ))}
                                  </select>
                                </div>
                              )}

                              {/* Actions */}
                              <div style={{ display: "flex", gap: 8, alignItems: "flex-end", paddingBottom: 2 }}>
                                <button
                                  disabled={rowSaving === entry.id}
                                  onClick={async () => {
                                    setRowSaving(entry.id);
                                    try {
                                      if (usingShare) {
                                        await patchCatalogEntry(entry.id, { harvest_key: sharedKey });
                                      } else {
                                        const base_url = urls.xml || urls.pdf || entry.easa_url;
                                        if (entry.harvest_source_id) {
                                          await updateSource(entry.harvest_source_id, { urls, base_url });
                                        } else {
                                          const created = await createSource({
                                            name: entry.short,
                                            external_id: entry.id,
                                            base_url,
                                            urls,
                                            format: "MIXED",
                                            frequency: "monthly",
                                            enabled: true,
                                          });
                                          await patchCatalogEntry(entry.id, { harvest_key: entry.id });
                                          void created;
                                        }
                                      }
                                      setExpandedRow(null);
                                      setRowSharedKey(prev => { const n = { ...prev }; delete n[entry.id]; return n; });
                                      await refreshData();
                                    } catch (err: any) { setError("Save failed: " + err.message); }
                                    finally { setRowSaving(null); }
                                  }}
                                  className="admin-action-btn admin-action-btn--save"
                                  style={{ padding: "6px 18px" }}
                                >
                                  {rowSaving === entry.id ? "Saving…" : entry.harvest_source_id ? "Update" : usingShare ? "Partager la source" : "Créer la source"}
                                </button>
                                <button onClick={() => { setExpandedRow(null); setRowSharedKey(prev => { const n = { ...prev }; delete n[entry.id]; return n; }); }} className="admin-action-btn">
                                  Annuler
                                </button>
                              </div>
                            </div>
                          </td>
                        </tr>
                        );
                      })()}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === "versions" && (
          <div className="admin-content">
            <h1 className="admin-page-title">Version Control</h1>
            <p className="admin-page-desc">Compare indexed document versions against the live EASA website. Snapshots are recorded automatically on each harvest run.</p>
            <div className="admin-cards-row" style={{ marginBottom: "1.5rem" }}>
              <BigStatCard value={stats?.version_snapshots_count ?? "-"} label="Snapshots" color="#7c3aed" />
              <BigStatCard value={stats?.harvest_runs_count ?? "-"} label="Harvest Runs" color="#007FC2" />
              <BigStatCard value={stats?.last_harvest_at ? new Date(stats.last_harvest_at).toLocaleDateString("fr-FR") : "Never"} label="Last Harvest" color="#16a34a" />
            </div>
            <div className="admin-card" style={{ maxWidth: 860 }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "1rem" }}>
                <h2 className="admin-card-title" style={{ margin: 0 }}>EASA Version Check</h2>
                <button className={"admin-primary-btn" + (versionCheckLoading ? " is-running" : "")} style={{ width: "auto", padding: "0.5rem 1.25rem" }} onClick={handleVersionCheck} disabled={versionCheckLoading}>
                  {versionCheckLoading ? "Checking..." : "Check EASA"}
                </button>
              </div>
              {versionCheckError && <div className="admin-error-banner" style={{ marginBottom: "0.75rem" }}>{versionCheckError}</div>}
              {versionChecks === null ? (
                <p style={{ color: "#9ca3af", fontSize: "0.82rem" }}>Click "Check EASA" to fetch current online versions for each indexed document.</p>
              ) : versionChecks.length === 0 ? (
                <p style={{ color: "#9ca3af", fontSize: "0.82rem" }}>No indexed documents found. Run a harvest first.</p>
              ) : (
                <table className="admin-table">
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Indexed version</th>
                      <th>Online version</th>
                      <th style={{ textAlign: "center" }}>Status</th>
                      <th>Checked at</th>
                    </tr>
                  </thead>
                  <tbody>
                    {versionChecks.map((vc) => (
                      <tr key={vc.source_root}>
                        <td>
                          <a href={vc.easa_url} target="_blank" rel="noreferrer" className="admin-link">{vc.source_title}</a>
                        </td>
                        <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{vc.indexed_version ?? "-"}</td>
                        <td style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>{vc.latest_version ?? "-"}</td>
                        <td style={{ textAlign: "center" }}>
                          {vc.is_outdated
                            ? <span className="admin-status-badge admin-status-badge--warn">Outdated</span>
                            : vc.latest_version
                              ? <span className="admin-status-badge admin-status-badge--ok">Up to date</span>
                              : <span className="admin-status-badge">Unknown</span>}
                        </td>
                        <td style={{ color: "#9ca3af", fontSize: "0.72rem", whiteSpace: "nowrap" }}>
                          {new Date(vc.checked_at).toLocaleTimeString("fr-FR")}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function BigStatCard({ value, label, color, loading }: { value: string | number | undefined; label: string; color: string; loading?: boolean }) {
  return (
    <div className="admin-big-stat" style={{ borderTopColor: color }}>
      {loading && value === undefined
        ? <span className="admin-big-stat-skeleton" />
        : <span className="admin-big-stat-value" style={{ color }}>{value ?? "—"}</span>
      }
      <span className="admin-big-stat-label">{label}</span>
    </div>
  );
}

function HealthRow({ label, ok, sublabel, error }: { label: string; ok?: boolean; sublabel?: string; error?: string | null }) {
  return (
    <div className="admin-health-row-wrap">
      <div className="admin-health-row" title={!ok && error ? error : undefined}>
        <span className={"admin-health-dot" + (ok ? " ok" : " err")} />
        <span className="admin-health-label">
          {label}
          {sublabel && <span className="admin-health-sublabel">{sublabel}</span>}
        </span>
        <span className={"admin-health-status" + (ok ? " ok" : " err")}>{ok ? "Online" : "Offline"}</span>
      </div>
      {!ok && error && (
        <div className="admin-health-error">{error}</div>
      )}
    </div>
  );
}

function KVRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="admin-kv-row">
      <span className="admin-kv-label">{label}</span>
      <span className="admin-kv-value">{String(value)}</span>
    </div>
  );
}