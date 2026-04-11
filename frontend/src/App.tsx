import { useEffect, useMemo, useState } from "react";
import { getNeighbors, getNode, listAllNodes } from "./api";
import { AdminConsole } from "./components/AdminConsole";
import { ArticlePanel } from "./components/ArticlePanel";
import { AskPanel } from "./components/AskPanel";
import { NeighborsPanel } from "./components/NeighborsPanel";
import { TreePanel } from "./components/TreePanel";
import { buildTree } from "./tree";
import type {
  NeighborsResponse,
  NodeDetail,
  NodeSummary,
} from "./types";

type AppMode = "explore" | "ask";

export default function App() {
  const [mode, setMode] = useState<AppMode>("explore");
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [allNodes, setAllNodes] = useState<NodeSummary[] | null>(null);
  const [rootError, setRootError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const [selected, setSelected] = useState<NodeSummary | null>(null);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [neighbors, setNeighbors] = useState<NeighborsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Load the full node listing on mount.
  useEffect(() => {
    listAllNodes()
      .then((resp) => {
        setAllNodes(resp.items);
        const defaultNode =
          resp.items.find((n) => n.reference_code === "21.A.91") ?? resp.items[0];
        if (defaultNode) setSelected(defaultNode);
      })
      .catch((err: Error) => setRootError(err.message));
  }, []);

  // Whenever the selection changes, fetch detail + neighbors in parallel.
  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    Promise.all([getNode(selected.node_id), getNeighbors(selected.node_id)])
      .then(([d, n]) => {
        if (cancelled) return;
        setDetail(d);
        setNeighbors(n);
      })
      .catch((err: Error) => {
        if (cancelled) return;
        setDetailError(err.message);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  const filteredNodes = useMemo(() => {
    if (!allNodes) return null;
    if (!searchQuery.trim()) return allNodes;
    const q = searchQuery.toLowerCase();
    return allNodes.filter(
      (n) =>
        n.reference_code.toLowerCase().includes(q) ||
        (n.title ?? "").toLowerCase().includes(q)
    );
  }, [allNodes, searchQuery]);

  const tree = useMemo(() => (filteredNodes ? buildTree(filteredNodes) : []), [filteredNodes]);

  // Set of bare IR reference codes (e.g. "21.A.20") that exist in our DB — used to
  // determine whether a cross-reference in article text is navigable.
  const knownRefs = useMemo(
    () => new Set((allNodes ?? []).filter((n) => n.node_type === "IR").map((n) => n.reference_code)),
    [allNodes]
  );

  function handleNavigateByRef(refCode: string) {
    if (!allNodes) return;
    const node = allNodes.find((n) => n.reference_code === refCode);
    if (node) { setSelected(node); setMode("explore"); }
  }

  function handleNavigateById(nodeId: string) {
    if (!allNodes) return;
    const node = allNodes.find((n) => n.node_id === nodeId);
    if (node) { setSelected(node); setMode("explore"); }
  }

  if (rootError) {
    return (
      <div className="root-error">
        <h1>Failed to load catalogue</h1>
        <p>{rootError}</p>
        <p>Is the API running on http://localhost:8000 ?</p>
      </div>
    );
  }
  if (!allNodes) {
    return <div className="root-loading">Loading catalogue…</div>;
  }

  return (
    <div className="app-root">
      <nav className="app-topbar">
        <span className="app-brand">Astra</span>
        <div className="app-tabs">
          <button
            className={"app-tab" + (mode === "explore" ? " is-active" : "")}
            onClick={() => setMode("explore")}
          >
            EXPLORE
          </button>
          <button
            className={"app-tab" + (mode === "ask" ? " is-active" : "")}
            onClick={() => setMode("ask")}
          >
            ASK
          </button>
        </div>
        <div style={{ marginLeft: "auto" }}>
          <button
            className="app-tab"
            style={{ 
              background: "rgba(255,255,255,0.1)", 
              border: "1px solid rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              gap: "0.5rem"
            }}
            onClick={() => setIsAdminOpen(true)}
          >
            <span style={{ fontSize: "1.1rem" }}>⚙️</span>
            CONSOLE
          </button>
        </div>
      </nav>

      {mode === "explore" ? (
        <div className="app-grid">
          <TreePanel
            tree={tree}
            selectedNodeId={selected?.node_id ?? null}
            onSelect={setSelected}
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
          />
          <ArticlePanel
            node={detail}
            loading={detailLoading}
            error={detailError}
            onNavigate={handleNavigateByRef}
            knownRefs={knownRefs}
          />
          <NeighborsPanel
            neighbors={neighbors}
            loading={detailLoading}
            onSelect={setSelected}
          />
        </div>
      ) : (
        <div className="app-ask">
          <AskPanel onNavigate={handleNavigateById} />
        </div>
      )}

      <AdminConsole isOpen={isAdminOpen} onClose={() => setIsAdminOpen(false)} />
    </div>
  );
}
