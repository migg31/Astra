import { useEffect, useState } from "react";
import { getHarvesterStatus, getHealth, getStats, getSystemConfig, startHarvester } from "../api";
import type { HealthStatus, IngestionStatus, SystemConfig, SystemStats } from "../types";

interface AdminConsoleProps {
  isOpen: boolean;
  onClose: () => void;
}

export function AdminConsole({ isOpen, onClose }: AdminConsoleProps) {
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [config, setConfig] = useState<SystemConfig | null>(null);
  const [harvester, setHarvester] = useState<IngestionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConfigExpanded, setIsConfigExpanded] = useState(false);

  const refreshData = async () => {
    try {
      const [s, h, i, c] = await Promise.all([
        getStats(),
        getHealth(),
        getHarvesterStatus(),
        getSystemConfig(),
      ]);
      setStats(s);
      setHealth(h);
      setHarvester(i);
      setConfig(c);
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
      await startHarvester();
      refreshData();
    } catch (err: any) {
      setError("Failed to start harvester: " + err.message);
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
              onClick={() => setIsConfigExpanded(!isConfigExpanded)} 
              style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '0.5rem', userSelect: 'none' }}
            >
              <span style={{ 
                fontSize: '0.6rem', 
                transition: 'transform 0.2s', 
                transform: isConfigExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                display: 'inline-block',
                width: '10px'
              }}>▶</span>
              Regulatory Sources
            </h3>
            {isConfigExpanded && (
              <div className="config-grid" style={{ marginTop: '0.5rem', paddingLeft: '1rem' }}>
                <ConfigItem label="Source Name" value={config?.harvester_name} />
                <ConfigItem label="Download URL" value={config?.harvester_source_url} isUrl />
              </div>
            )}
          </section>

          <section className="admin-section">
            <h3>Knowledge Harvester</h3>
            <div className="harvester-card">
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

function ConfigItem({ label, value, isUrl }: { label: string; value?: string; isUrl?: boolean }) {
  return (
    <div className="config-item">
      <span className="config-label">{label}</span>
      <span className="config-value" title={value}>
        {isUrl ? <a href={value} target="_blank" rel="noreferrer">{value}</a> : value ?? "-"}
      </span>
    </div>
  );
}
