import React, { useEffect, useState } from "react";
import {
  createSource, deleteSource, getHarvesterStatus, getHealth, getStats,
  getSystemConfig, listHarvesterSources, listSources, startHarvester, updateSource,
} from "../api";
import type { HealthStatus, IngestionStatus, RegulatorySource, SystemConfig, SystemStats } from "../types";

interface AdminConsoleProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AdminConsole({ isOpen, onClose }: AdminConsoleProps) {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [_config, setConfig] = useState<SystemConfig | null>(null);
  const [harvester, setHarvester] = useState<IngestionStatus | null>(null);
  const [sources, setSources] = useState<{ id: string; name: string; external_id: string; enabled: boolean }[]>([]);
  const [selectedSource, setSelectedSource] = useState("part21");
  const [error, setError] = useState<string | null>(null);
  const [isSourcesExpanded, setIsSourcesExpanded] = useState(false);
  const [regulatorySources, setRegulatorySources] = useState<RegulatorySource[]>([]);
  const [editingSource, setEditingSource] = useState<RegulatorySource | null>(null);
  const [addingSource, setAddingSource] = useState(false);
  const [newSource, setNewSource] = useState({ name: "", base_url: "", external_id: "", format: "MIXED", frequency: "monthly", enabled: true });

  const refreshData = async () => {
    try {
      const [s, h, i, c, src, regSrc] = await Promise.all([
        getStats(),
        getHealth(),
        getHarvesterStatus(),
        getSystemConfig(),
        listHarvesterSources(),
        listSources(),
      ]);
      setStats(s);
      setHealth(h);
      setHarvester(i);
      setConfig(c);
      setSources(src);
      setRegulatorySources(regSrc);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    }
  };

  useEffect(() => {
    if (isOpen) {
      refreshData();
      const interval = setInterval(refreshData, 5000);
      return () => clearInterval(interval);
    }
  }, [isOpen]);

  const handleRunHarvester = async () => {
    try {
      await startHarvester(selectedSource);
      refreshData();
    } catch (err: any) {
      setError("Failed to start harvester: " + err.message);
    }
  };

  const handleToggleEnabled = async (src: RegulatorySource) => {
    try {
      await updateSource(src.source_id, { enabled: !src.enabled });
      await refreshData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleSaveEdit = async () => {
    if (!editingSource) return;
    try {
      await updateSource(editingSource.source_id, {
        name: editingSource.name,
        base_url: editingSource.base_url,
      });
      setEditingSource(null);
      await refreshData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleDelete = async (src: RegulatorySource) => {
    if (!confirm(`Delete "${src.name}"?`)) return;
    try {
      await deleteSource(src.source_id);
      await refreshData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  const handleAddSource = async () => {
    try {
      await createSource(newSource);
      setAddingSource(false);
      setNewSource({ name: "", base_url: "", external_id: "", format: "MIXED", frequency: "monthly", enabled: true });
      await refreshData();
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className={`admin-console-overlay ${isOpen ? "is-open" : ""}`} onClick={onClose}>
      <div className="admin-console-panel" onClick={(e) => e.stopPropagation()}>
        <header className="admin-console-header">
          <h2>Admin Console</h2>
          <button className="admin-console-close" onClick={onClose}>
            &times;
          </button>
        </header>

        <div className="admin-console-body">
          {error && <div className="ask-error">{error}</div>}

          <section className="admin-section">
            <h3>System Health</h3>
            <div className="health-list">
              <HealthItem label="PostgreSQL" ok={health?.postgres} />
              <HealthItem label="ChromaDB" ok={health?.chroma} />
              <div style={{ height: '0.75rem' }} />
              <HealthItem label="Ollama Server" ok={health?.ollama_server} hasChild />
              <HealthItem label="Chat Model (mistral)" ok={health?.ollama_model_chat} isSubItem />
              <HealthItem label="Embed Model (nomic)" ok={health?.ollama_model_embed} isSubItem isLast />
            </div>
          </section>

          <section className="admin-section">
            <h3>Statistics</h3>
            
            <div className="stats-group-label">Regulatory Content</div>
            <div className="stats-grid">
              <StatCard label="Documents" value={stats?.documents_count} icon="📄" />
              <StatCard label="Nodes" value={stats?.nodes_count} icon="🧩" />
              <StatCard label="Relations" value={stats?.edges_count} icon="🔗" />
              <StatCard label="SQL Size" value={stats?.db_size_mb ? `${stats.db_size_mb} MB` : "-"} icon="💾" />
            </div>

            <div className="stats-group-label" style={{ marginTop: '1.5rem' }}>AI & Search Layer</div>
            <div className="stats-grid">
              <StatCard label="Embeddings" value={stats?.embeddings_count} icon="🧠" />
              <StatCard label="Vector Size" value={stats?.vector_size_mb ? `${stats.vector_size_mb} MB` : "-"} icon="📁" />
            </div>
          </section>

          <section className="admin-section">
            <h3
              onClick={() => setIsSourcesExpanded(!isSourcesExpanded)}
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', userSelect: 'none' }}
            >
              <span style={{
                fontSize: '0.6rem', transition: 'transform 0.2s',
                transform: isSourcesExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                display: 'inline-block', width: '10px'
              }}>▶</span>
              Regulatory Sources
              <span style={{ marginLeft: 'auto', fontSize: '0.7rem', color: '#6b7280', fontWeight: 400 }}>
                {regulatorySources.filter(s => s.enabled).length}/{regulatorySources.length} active
              </span>
            </h3>

            {isSourcesExpanded && (
              <div style={{ marginTop: '0.5rem' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.72rem' }}>
                  <thead>
                    <tr style={{ borderBottom: '1px solid #e5e7eb', color: '#6b7280' }}>
                      <th style={{ textAlign: 'left', padding: '0.3rem 0.4rem', fontWeight: 600 }}>Name</th>
                      <th style={{ textAlign: 'left', padding: '0.3rem 0.4rem', fontWeight: 600 }}>URL</th>
                      <th style={{ textAlign: 'center', padding: '0.3rem 0.4rem', fontWeight: 600 }}>Active</th>
                      <th style={{ textAlign: 'right', padding: '0.3rem 0.4rem', fontWeight: 600 }}>Last sync</th>
                      <th style={{ padding: '0.3rem 0.4rem' }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {regulatorySources.map(src => (
                      <tr key={src.source_id} style={{ borderBottom: '1px solid #f3f4f6' }}>
                        {editingSource?.source_id === src.source_id ? (
                          <>
                            <td style={{ padding: '0.3rem 0.4rem' }}>
                              <input
                                value={editingSource.name}
                                onChange={e => setEditingSource({ ...editingSource, name: e.target.value })}
                                style={{ width: '100%', fontSize: '0.72rem', padding: '0.15rem 0.3rem', border: '1px solid #d1d5db', borderRadius: 4 }}
                              />
                            </td>
                            <td style={{ padding: '0.3rem 0.4rem' }}>
                              <input
                                value={editingSource.base_url}
                                onChange={e => setEditingSource({ ...editingSource, base_url: e.target.value })}
                                style={{ width: '100%', fontSize: '0.72rem', padding: '0.15rem 0.3rem', border: '1px solid #d1d5db', borderRadius: 4 }}
                              />
                            </td>
                            <td colSpan={2} />
                            <td style={{ padding: '0.3rem 0.4rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                              <button onClick={handleSaveEdit} style={btnStyle('#16CC7F')}>Save</button>
                              <button onClick={() => setEditingSource(null)} style={{ ...btnStyle('#6b7280'), marginLeft: 4 }}>Cancel</button>
                            </td>
                          </>
                        ) : (
                          <>
                            <td style={{ padding: '0.3rem 0.4rem', color: src.enabled ? '#111827' : '#9ca3af' }}>{src.name}</td>
                            <td style={{ padding: '0.3rem 0.4rem', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              <a href={src.base_url} target="_blank" rel="noreferrer" style={{ color: '#007FC2', textDecoration: 'none' }} title={src.base_url}>
                                {src.external_id ?? src.base_url}
                              </a>
                            </td>
                            <td style={{ padding: '0.3rem 0.4rem', textAlign: 'center' }}>
                              <button
                                onClick={() => handleToggleEnabled(src)}
                                style={{
                                  background: src.enabled ? '#16CC7F' : '#e5e7eb',
                                  border: 'none', borderRadius: 10, width: 32, height: 16,
                                  cursor: 'pointer', position: 'relative', transition: 'background 0.2s'
                                }}
                                title={src.enabled ? 'Enabled — click to disable' : 'Disabled — click to enable'}
                              >
                                <span style={{
                                  position: 'absolute', top: 2, left: src.enabled ? 18 : 2,
                                  width: 12, height: 12, borderRadius: '50%', background: '#fff',
                                  transition: 'left 0.2s'
                                }} />
                              </button>
                            </td>
                            <td style={{ padding: '0.3rem 0.4rem', textAlign: 'right', color: '#9ca3af', whiteSpace: 'nowrap' }}>
                              {src.last_sync_at ? new Date(src.last_sync_at).toLocaleDateString() : '—'}
                            </td>
                            <td style={{ padding: '0.3rem 0.4rem', textAlign: 'right', whiteSpace: 'nowrap' }}>
                              <button onClick={() => setEditingSource(src)} style={btnStyle('#6b7280')} title="Edit">✎</button>
                              <button onClick={() => handleDelete(src)} style={{ ...btnStyle('#ef4444'), marginLeft: 4 }} title="Delete">✕</button>
                            </td>
                          </>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>

                {addingSource ? (
                  <div style={{ marginTop: '0.75rem', padding: '0.5rem', background: '#f9fafb', borderRadius: 6, fontSize: '0.72rem' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.4rem', marginBottom: '0.4rem' }}>
                      <input placeholder="Name" value={newSource.name} onChange={e => setNewSource({ ...newSource, name: e.target.value })} style={inputStyle} />
                      <input placeholder="external_id (e.g. easa-cs23)" value={newSource.external_id} onChange={e => setNewSource({ ...newSource, external_id: e.target.value })} style={inputStyle} />
                      <input placeholder="Download URL" value={newSource.base_url} onChange={e => setNewSource({ ...newSource, base_url: e.target.value })} style={{ ...inputStyle, gridColumn: 'span 2' }} />
                    </div>
                    <button onClick={handleAddSource} style={btnStyle('#222F64')}>Add</button>
                    <button onClick={() => setAddingSource(false)} style={{ ...btnStyle('#6b7280'), marginLeft: 4 }}>Cancel</button>
                  </div>
                ) : (
                  <button
                    onClick={() => setAddingSource(true)}
                    style={{ marginTop: '0.5rem', fontSize: '0.72rem', color: '#007FC2', background: 'none', border: 'none', cursor: 'pointer', padding: '0.2rem 0' }}
                  >
                    + Add source
                  </button>
                )}
              </div>
            )}
          </section>

          <section className="admin-section">
            <h3>Knowledge Harvester</h3>
            <div className="harvester-card">
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.7rem', fontWeight: 600, color: '#6b7280', marginBottom: '0.25rem' }}>
                  Select Regulatory Source
                </label>
                <select 
                  value={selectedSource}
                  onChange={(e) => setSelectedSource(e.target.value)}
                  disabled={harvester?.is_running}
                  style={{
                    width: '100%',
                    padding: '0.4rem',
                    borderRadius: '6px',
                    border: '1px solid #e5e7eb',
                    fontSize: '0.75rem',
                    background: '#fff',
                    color: '#222F64',
                    outline: 'none'
                  }}
                >
                  {sources.map(s => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>

              <div className="harvester-status">
                <strong>Status:</strong>{" "}
                {harvester?.is_running ? (
                  <span style={{ color: "#007FC2", fontWeight: 700 }}>RUNNING...</span>
                ) : (
                  <span style={{ color: "#6b7280" }}>IDLE</span>
                )}
              </div>
              
              <button
                className="harvester-run-btn"
                onClick={handleRunHarvester}
                disabled={harvester?.is_running}
              >
                {harvester?.is_running ? "Ingestion in Progress..." : "Run Harvester (Sync EASA)"}
              </button>

              {(harvester?.is_running || harvester?.error || harvester?.last_report) && (
                <div className="harvester-log">
                  {harvester?.error && `ERROR: ${harvester.error}\n`}
                  {harvester?.last_report && 
                    `Last Success: ${new Date(harvester.last_run_at!).toLocaleString()}\n` +
                    `Nodes: ${harvester.last_report.nodes}\n` +
                    `Edges: ${harvester.last_report.edges_inserted}\n`
                  }
                  {harvester?.is_running && !harvester.error && "Executing pipeline...\n- Fetching XML\n- Parsing\n- Upserting Postgres\n- Re-indexing Vectors"}
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function HealthItem({ label, ok, isSubItem, isLast, hasChild }: { 
  label: string; ok?: boolean; isSubItem?: boolean; isLast?: boolean; hasChild?: boolean 
}) {
  const rowHeight = '1.4rem';
  const dotSize = isSubItem ? 6 : 8;
  const lineX = 4; // Point de 8px -> centre à 4px
  
  return (
    <div className="health-item" style={{ 
      position: 'relative', 
      paddingLeft: isSubItem ? '1.5rem' : '0',
      height: rowHeight,
      display: 'flex',
      alignItems: 'center',
      gap: '0.75rem'
    }}>
      {(isSubItem || hasChild) && (
        <>
          {/* Ligne verticale (tige) centrée sur lineX */}
          <div style={{
            position: 'absolute',
            left: `${lineX}px`,
            top: hasChild ? '50%' : 0,
            bottom: isLast ? '50%' : 0,
            width: '1.5px',
            background: '#d1d5db',
            zIndex: 0,
            transform: 'translateX(-50%)' // Pour centrer l'épaisseur de 1.5px
          }} />
          
          {/* Ligne horizontale (connecteur) de lineX jusqu'au point de l'enfant */}
          {isSubItem && (
            <div style={{
              position: 'absolute',
              left: `${lineX}px`,
              top: '50%',
              width: `${1.5 * 16 - lineX + 2}px`, // De lineX jusqu'à la pastille (1.5rem = 24px)
              height: '1.5px',
              background: '#d1d5db',
              zIndex: 0,
              transform: 'translateY(-50%)'
            }} />
          )}
        </>
      )}
      
      <div className={`health-dot ${ok ? "ok" : "error"}`} 
           style={{ 
             width: `${dotSize}px`, 
             height: `${dotSize}px`, 
             zIndex: 1,
             flexShrink: 0,
             marginLeft: isSubItem ? '2px' : 0 // Ajustement pour que le centre du point de 8px soit aligné visuellement
           }} />
           
      <span style={{ 
        fontSize: isSubItem ? '0.8125rem' : '0.875rem', 
        color: isSubItem ? '#4b5563' : 'inherit',
        lineHeight: rowHeight,
        display: 'inline-block',
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis'
      }}>
        {label}
      </span>
      
      <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: ok ? "#16CC7F" : "#ef4444", zIndex: 1, flexShrink: 0 }}>
        {ok ? "ONLINE" : "OFFLINE"}
      </span>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value?: string | number; icon?: string }) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.25rem' }}>
        <span style={{ fontSize: '1.2rem' }}>{icon}</span>
        <span className="stat-value" style={{ marginBottom: 0 }}>{value ?? "-"}</span>
      </div>
      <span className="stat-label">{label}</span>
    </div>
  );
}

const btnStyle = (color: string): React.CSSProperties => ({
  fontSize: '0.68rem', padding: '0.15rem 0.4rem', border: `1px solid ${color}`,
  borderRadius: 4, background: 'none', color, cursor: 'pointer',
});

const inputStyle: React.CSSProperties = {
  fontSize: '0.72rem', padding: '0.2rem 0.4rem',
  border: '1px solid #d1d5db', borderRadius: 4, width: '100%',
};

