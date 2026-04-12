import { useEffect, useMemo, useState } from "react";
import { getGraph, getNeighbors, getNode, listAllNodes } from "./api";
import { AdminConsole } from "./components/AdminConsole";
import { ArticlePanel } from "./components/ArticlePanel";
import { AskPanel } from "./components/AskPanel";
import { MapPanel } from "./components/MapPanel";
import { NeighborsPanel } from "./components/NeighborsPanel";
import { TreePanel } from "./components/TreePanel";
import { articleCode, buildDocuments, buildTree, typeOrder } from "./tree";
import type {
  DocumentInfo,
  GraphData,
  NeighborsResponse,
  NodeDetail,
  NodeSummary,
  NodeType,
} from "./types";

type AppMode = "explore" | "ask" | "map";

export default function App() {
  const [mode, setMode] = useState<AppMode>("explore");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [isAdminOpen, setIsAdminOpen] = useState(false);
  const [allNodes, setAllNodes] = useState<NodeSummary[] | null>(null);
  const [rootError, setRootError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Explorer state
  const [selected, setSelected] = useState<NodeSummary | null>(null);
  const [detail, setDetail] = useState<NodeDetail | null>(null);
  const [neighbors, setNeighbors] = useState<NeighborsResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  // Document & type filter state
  const [selectedSource, setSelectedSource] = useState<string | null>(null);
  const [activeTypes, setActiveTypes] = useState<Set<NodeType>>(
    new Set(["IR", "AMC", "GM", "CS"])
  );

  // ── Load nodes ──
  useEffect(() => {
    listAllNodes()
      .then((resp) => {
        setAllNodes(resp.items);
        // Auto-select first document
        const docs = buildDocuments(resp.items);
        if (docs.length > 0) setSelectedSource(docs[0].source);
        // Auto-select default article
        const defaultNode =
          resp.items.find((n) => n.reference_code === "21.A.91") ?? resp.items[0];
        if (defaultNode) setSelected(defaultNode);
      })
      .catch((err: Error) => setRootError(err.message));
  }, []);

  // ── Fetch article detail on selection ──
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
    return () => { cancelled = true; };
  }, [selected]);

  // ── Derived data ──

  const documents: DocumentInfo[] = useMemo(
    () => (allNodes ? buildDocuments(allNodes) : []),
    [allNodes]
  );

  /**
   * Types actually present in the selected document — computed BEFORE activeTypes
   * filtering so pills never disappear when a type is toggled off.
   */
  const availableTypes = useMemo<NodeType[]>(() => {
    if (!allNodes) return [];
    const docNodes = selectedSource
      ? allNodes.filter((n) => n.hierarchy_path.split(" / ")[0] === selectedSource)
      : allNodes;
    return (["IR", "AMC", "GM", "CS"] as NodeType[]).filter((t) =>
      docNodes.some((n) => n.node_type === t)
    );
  }, [allNodes, selectedSource]);

  /** Nodes scoped to selected document + active types + search query. */
  const filteredNodes = useMemo(() => {
    if (!allNodes) return null;
    let nodes = allNodes;
    if (selectedSource) {
      nodes = nodes.filter((n) => (n.hierarchy_path.split(" / ")[0] ?? "Unknown") === selectedSource);
    }
    nodes = nodes.filter((n) => n.node_type === "GROUP" || activeTypes.has(n.node_type));
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      nodes = nodes.filter(
        (n) =>
          n.reference_code.toLowerCase().includes(q) ||
          (n.title ?? "").toLowerCase().includes(q)
      );
    }
    return nodes;
  }, [allNodes, selectedSource, activeTypes, searchQuery]);

  const tree = useMemo(
    () => (filteredNodes ? buildTree(filteredNodes) : []),
    [filteredNodes]
  );

  /** All IR nodes — used by ArticlePanel to detect navigable cross-references. */
  const knownRefs = useMemo(
    () => new Set((allNodes ?? []).filter((n) => n.node_type === "IR").map((n) => n.reference_code)),
    [allNodes]
  );

  /** All variants (IR/AMC/GM) for the same article as the selected node. */
  const articleSiblings = useMemo<NodeSummary[]>(() => {
    if (!selected || !allNodes) return [];
    const art = articleCode(selected);
    const selectedDoc = selected.hierarchy_path.split(" / ")[0];
    return allNodes
      .filter(
        (n) =>
          n.node_type !== "GROUP" &&
          articleCode(n) === art &&
          n.hierarchy_path.split(" / ")[0] === selectedDoc
      )
      .sort((a, b) => typeOrder(a.node_type) - typeOrder(b.node_type));
  }, [selected, allNodes]);

  // ── Handlers ──

  function handleModeChange(m: AppMode) {
    setMode(m);
    if (m === "map" && !graphData) {
      getGraph().then(setGraphData).catch(console.error);
    }
  }

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

  function handleToggleType(type: NodeType) {
    setActiveTypes((prev) => {
      const next = new Set(prev);
      // Keep at least one type active
      if (next.has(type) && next.size === 1) return prev;
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  function handleSelectSource(source: string) {
    setSelectedSource(source);
    setSearchQuery("");
  }

  // ── Render ──

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
            onClick={() => handleModeChange("explore")}
          >
            EXPLORE
          </button>
          <button
            className={"app-tab" + (mode === "ask" ? " is-active" : "")}
            onClick={() => handleModeChange("ask")}
          >
            ASK
          </button>
          <button
            className={"app-tab" + (mode === "map" ? " is-active" : "")}
            onClick={() => handleModeChange("map")}
          >
            MAP
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
              gap: "0.5rem",
            }}
            onClick={() => setIsAdminOpen(true)}
          >
            <span style={{ fontSize: "1.1rem" }}>⚙️</span>
            CONSOLE
          </button>
        </div>
      </nav>

      {mode === "explore" && (
        <div className="app-grid">
          <TreePanel
            documents={documents}
            selectedSource={selectedSource}
            onSelectSource={handleSelectSource}
            availableTypes={availableTypes}
            activeTypes={activeTypes}
            onToggleType={handleToggleType}
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
            siblings={articleSiblings}
            onSelectSibling={setSelected}
          />
          <NeighborsPanel
            neighbors={neighbors}
            loading={detailLoading}
            onSelect={setSelected}
          />
        </div>
      )}
      {mode === "ask" && (
        <div className="app-ask">
          <AskPanel onNavigate={handleNavigateById} />
        </div>
      )}
      {mode === "map" && (
        <MapPanel
          graphData={graphData}
          selectedNodeId={selected?.node_id ?? null}
          onNavigate={handleNavigateById}
        />
      )}

      <AdminConsole isOpen={isAdminOpen} onClose={() => setIsAdminOpen(false)} />
    </div>
  );
}
