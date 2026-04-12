import { useEffect, useState } from "react";
import {
  createSource, deleteSource, getHarvesterStatus, getHealth, getStats,
  getSystemConfig, getVersionCheck, listHarvesterSources, listSources, startHarvester, updateSource,
} from "../api";
import type { VersionCheckResult } from "../api";
import type { HealthStatus, IngestionStatus, RegulatorySource, SystemStats } from "../types";

type AdminTab = "overview" | "harvest" | "sources" | "versions";

interface AdminConsoleProps {
  onClose: () => void;
}

export function AdminConsole({ onClose }: AdminConsoleProps) {
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [harvester, setHarvester] = useState<IngestionStatus | null>(null);
  const [sources, setSources] = useState<{ id: string; name: string; external_id: string; enabled: boolean }[]>([]);
  const [selectedSource, setSelectedSource] = useState("part21");
  const [error, setError] = useState<string | null>(null);
  const [regulatorySources, setRegulatorySources] = useState<RegulatorySource[]>([]);
  const [editingSource, setEditingSource] = useState<RegulatorySource | null>(null);
  const [addingSource, setAddingSource] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", base_url: "", external_id: "", format: "MIXED", frequency: "monthly", enabled: true });
  const [versionChecks, setVersionChecks] = useState<VersionCheckResult[] | null>(null);
  const [versionCheckLoading, setVersionCheckLoading] = useState(false);
  const [versionCheckError, setVersionCheckError] = useState<string | null>(null);

  const refreshData = async () => {
    try {
      const [s, h, i, , src, regSrc] = await Promise.all([
        getStats(), getHealth(), getHarvesterStatus(), getSystemConfig(),
        listHarvesterSources(), listSources(),
      ]);
      setStats(s); setHealth(h); setHarvester(i);
      setSources(src); setRegulatorySources(regSrc);
      setError(null);
    } catch (err: any) { setError(err.message); }
  };

  useEffect(() => {
    refreshData();
    const iv = setInterval(refreshData, 8000);
    return () => clearInterval(iv);
  }, []);

  const handleVersionCheck = async () => {
    setVersionCheckLoading(true); setVersionCheckError(null);
    try { setVersionChecks(await getVersionCheck()); }
    catch (err: any) { setVersionCheckError(err.message); }
    finally { setVersionCheckLoading(false); }
  };

  const handleRunHarvester = async () => {
    try { await startHarvester(selectedSource); refreshData(); }
    catch (err: any) { setError("Harvester failed: " + err.message); }
  };

  const handleToggleEnabled = async (src: RegulatorySource) => {
    try { await updateSource(src.source_id, { enabled: !src.enabled }); await refreshData(); }
    catch (err: any) { setError(err.message); }
  };

  const handleSaveEdit = async () => {
    if (!editingSource) return;
    try {
      await updateSource(editingSource.source_id, { name: editingSource.name, base_url: editingSource.base_url });
      setEditingSource(null); await refreshData();
    } catch (err: any) { setError(err.message); }
  };

  const handleDelete = async (src: RegulatorySource) => {
    if (!confirm("Delete " + src.name + "?")) return;
    try { await deleteSource(src.source_id); await refreshData(); }
    catch (err: any) { setError(err.message); }
  };

  const handleAddSource = async () => {
    try {
      await createSource(newSource);
      setAddingSource(false);
      setNewSource({ name: "", base_url: "", external_id: "", format: "MIXED", frequency: "monthly", enabled: true });
      await refreshData();
    } catch (err: any) { setError(err.message); }
  };

  const TABS: { id: AdminTab; label: string; icon: string }[] = [
    { id: "overview", label: "Overview", icon: "O" },
    { id: "harvest",  label: "Harvest",  icon: "H" },
    { id: "sources",  label: "Sources",  icon: "S" },
    { id: "versions", label: "Versions", icon: "V" },
  ];

  return (
    <div className="admin-page">
      <aside className="admin-sidebar">
        <div className="admin-sidebar-brand">Admin Console</div>
        <nav className="admin-sidebar-nav">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={"admin-nav-item" + (activeTab === t.id ? " is-active" : "")}
              onClick={() => setActiveTab(t.id)}
            >
              <span className="admin-nav-icon">{t.icon}</span>
              <span>{t.label}</span>
            </button>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          <button className="admin-back-btn" onClick={onClose}>Back to app</button>
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
            <h1 className="admin-page-title">Overview</h1>
            <div className="admin-cards-row">
              <BigStatCard value={stats?.nodes_count ?? "-"} label="Regulatory Nodes" color="#222F64" />
              <BigStatCard value={stats?.documents_count ?? "-"} label="Documents" color="#007FC2" />
              <BigStatCard value={stats?.edges_count ?? "-"} label="Relations" color="#16a34a" />
              <BigStatCard value={stats?.embeddings_count ?? "-"} label="Embeddings" color="#7c3aed" />
            </div>
            <div className="admin-two-col">
              <div className="admin-card">
                <h2 className="admin-card-title">System Health</h2>
                <div className="admin-health-grid">
                  <HealthRow label="PostgreSQL" ok={health?.postgres} />
                  <HealthRow label="ChromaDB" ok={health?.chroma} />
                  <HealthRow label="Ollama Server" ok={health?.ollama_server} />
                  <HealthRow label="Chat Model" ok={health?.ollama_model_chat} />
                  <HealthRow label="Embed Model" ok={health?.ollama_model_embed} />
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
            <p className="admin-page-desc">Fetch and ingest EASA XML into PostgreSQL and re-index vectors. Version snapshots are recorded automatically for every changed node.</p>
            <div className="admin-card" style={{ maxWidth: 560 }}>
              <h2 className="admin-card-title">Run Ingestion</h2>
              <label className="admin-label">Regulatory Source</label>
              <select className="admin-select" value={selectedSource} onChange={(e) => setSelectedSource(e.target.value)} disabled={harvester?.is_running}>
                {sources.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
              <div className="admin-status-row">
                <span className="admin-label" style={{ margin: 0 }}>Status</span>
                {harvester?.is_running
                  ? <span className="admin-badge admin-badge--running">RUNNING</span>
                  : <span className="admin-badge admin-badge--idle">IDLE</span>}
              </div>
              <button className={"admin-primary-btn" + (harvester?.is_running ? " is-running" : "")} onClick={handleRunHarvester} disabled={harvester?.is_running}>
                {harvester?.is_running ? "Ingestion in progress..." : "Run Harvester"}
              </button>
              {(harvester?.error || harvester?.last_report || harvester?.is_running) && (
                <pre className="admin-log">
                  {harvester?.error
                    ? "ERROR: " + harvester.error
                    : harvester?.is_running
                      ? "Pipeline running...\n  Fetching XML\n  Parsing\n  Upserting PostgreSQL\n  Re-indexing vectors"
                      : harvester?.last_report
                        ? "Completed " + new Date(harvester.last_run_at!).toLocaleString("fr-FR") + "\n  Nodes : " + harvester.last_report.nodes + "\n  Edges : " + harvester.last_report.edges_inserted
                        : ""}
                </pre>
              )}
            </div>
          </div>
        )}

        {activeTab === "sources" && (
          <div className="admin-content">
            <h1 className="admin-page-title">Regulatory Sources</h1>
            <p className="admin-page-desc">{regulatorySources.filter(s => s.enabled).length} / {regulatorySources.length} sources active.</p>
            <div className="admin-card">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>External ID</th>
                    <th>URL</th>
                    <th style={{ textAlign: "center" }}>Active</th>
                    <th>Last sync</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {regulatorySources.map(src => (
                    <tr key={src.source_id} className={src.enabled ? "" : "admin-table-row--dim"}>
                      {editingSource?.source_id === src.source_id ? (
                        <>
                          <td><input className="admin-input-inline" value={editingSource.name} onChange={e => setEditingSource({ ...editingSource, name: e.target.value })} /></td>
                          <td></td>
                          <td><input className="admin-input-inline" value={editingSource.base_url} onChange={e => setEditingSource({ ...editingSource, base_url: e.target.value })} /></td>
                          <td></td><td></td>
                          <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                            <button onClick={handleSaveEdit} className="admin-action-btn admin-action-btn--save">Save</button>
                            <button onClick={() => setEditingSource(null)} className="admin-action-btn" style={{ marginLeft: 6 }}>Cancel</button>
                          </td>
                        </>
                      ) : (
                        <>
                          <td>{src.name}</td>
                          <td style={{ color: "#6b7280", fontFamily: "monospace", fontSize: "0.75rem" }}>{src.external_id}</td>
                          <td>
                            <a href={src.base_url} target="_blank" rel="noreferrer" className="admin-link" title={src.base_url}>
                              {src.base_url.replace(/^https?:\/\//, "").slice(0, 40)}
                            </a>
                          </td>
                          <td style={{ textAlign: "center" }}>
                            <button onClick={() => handleToggleEnabled(src)} className={"admin-toggle" + (src.enabled ? " is-on" : "")} title={src.enabled ? "Enabled" : "Disabled"}>
                              <span className="admin-toggle-thumb" />
                            </button>
                          </td>
                          <td style={{ color: "#9ca3af", whiteSpace: "nowrap" }}>
                            {src.last_sync_at ? new Date(src.last_sync_at).toLocaleDateString("fr-FR") : "-"}
                          </td>
                          <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                            <button onClick={() => setEditingSource(src)} className="admin-action-btn" title="Edit">Edit</button>
                            <button onClick={() => handleDelete(src)} className="admin-action-btn admin-action-btn--danger" title="Delete" style={{ marginLeft: 4 }}>Del</button>
                          </td>
                        </>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
              {addingSource ? (
                <div className="admin-add-form">
                  <div className="admin-add-form-grid">
                    <input className="admin-input" placeholder="Name" value={newSource.name} onChange={e => setNewSource({ ...newSource, name: e.target.value })} />
                    <input className="admin-input" placeholder="External ID" value={newSource.external_id} onChange={e => setNewSource({ ...newSource, external_id: e.target.value })} />
                    <input className="admin-input admin-input--full" placeholder="Download URL" value={newSource.base_url} onChange={e => setNewSource({ ...newSource, base_url: e.target.value })} />
                  </div>
                  <button onClick={handleAddSource} className="admin-action-btn admin-action-btn--save">Add</button>
                  <button onClick={() => setAddingSource(false)} className="admin-action-btn" style={{ marginLeft: 6 }}>Cancel</button>
                </div>
              ) : (
                <button onClick={() => setAddingSource(true)} className="admin-add-row-btn">+ Add source</button>
              )}
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

function BigStatCard({ value, label, color }: { value: string | number; label: string; color: string }) {
  return (
    <div className="admin-big-stat" style={{ borderTopColor: color }}>
      <span className="admin-big-stat-value" style={{ color }}>{value}</span>
      <span className="admin-big-stat-label">{label}</span>
    </div>
  );
}

function HealthRow({ label, ok }: { label: string; ok?: boolean }) {
  return (
    <div className="admin-health-row">
      <span className={"admin-health-dot" + (ok ? " ok" : " err")} />
      <span className="admin-health-label">{label}</span>
      <span className={"admin-health-status" + (ok ? " ok" : " err")}>{ok ? "Online" : "Offline"}</span>
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