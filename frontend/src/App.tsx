import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getCatalog, getGraph, getNeighbors, getNode, getVersionCheck, listAllNodes } from "./api";
import type { CatalogEntry, VersionCheckResult } from "./api";
import { AdminConsole } from "./components/AdminConsole";
import { ArticlePanel } from "./components/ArticlePanel";
import { AskPanel } from "./components/AskPanel";
import { MapPanel } from "./components/MapPanel";
import { NavigatePanel } from "./components/NavigatePanel";
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

type AppMode = "navigate" | "consult" | "ask" | "map" | "admin";

export default function App() {
  const [mode, setMode] = useState<AppMode>("navigate");
  const [graphData, setGraphData] = useState<GraphData | null>(null);
  const [catalog, setCatalog] = useState<CatalogEntry[]>([]);
  const [versionChecks, setVersionChecks] = useState<VersionCheckResult[]>([]);
  const [_isAdminOpen, _setIsAdminOpen] = useState(false);
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

  // ── Load catalog ──
  useEffect(() => {
    getCatalog().then(setCatalog).catch(console.error);
  }, []);

  // ── Version staleness check (runs once on mount, non-blocking) ──
  useEffect(() => {
    getVersionCheck().then(setVersionChecks).catch(() => {});
  }, []);

  // ── Load nodes ──
  useEffect(() => {
    listAllNodes()
      .then((resp) => {
        setAllNodes(resp.items);
        // Auto-select first document
        const docs = buildDocuments(resp.items);
        if (docs.length > 0) setSelectedSource(docs[0].source);
        // Auto-select default article
        const defaultNode = resp.items[0];
        if (defaultNode) setSelected(defaultNode);
      })
      .catch((err: Error) => {
        // Even if nodes fail to load, show the Navigate panel with catalog
        setAllNodes([]);
        setRootError(err.message);
      });
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
    () => new Set((allNodes ?? []).map((n) => n.reference_code)),
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

  /** Called from NavigatePanel when user clicks an indexed doc → switch to Consult.
   *  source is the exact hierarchy_path root (source_root from catalog API). */
  function handleNavigateToSource(source: string) {
    handleSelectSource(source);
    setMode("consult");
  }

  function handleNavigateByRef(refCode: string) {
    if (!allNodes) return;
    const node = allNodes.find((n) => n.reference_code === refCode);
    if (node) { setSelected(node); setMode("consult"); }
  }

  function handleNavigateById(nodeId: string) {
    if (!allNodes) return;
    const node = allNodes.find((n) => n.node_id === nodeId);
    if (node) { setSelected(node); setMode("consult"); }
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
    // Auto-select the first IR node of the new document
    if (allNodes) {
      const docNodes = allNodes.filter(
        (n) => n.hierarchy_path.split(" / ")[0] === source && n.node_type !== "GROUP"
      );
      const firstIR = docNodes.find((n) => n.node_type === "IR") ?? docNodes[0] ?? null;
      setSelected(firstIR);
    }
  }

  // ── Resizable left panel ──
  const [leftWidth, setLeftWidth] = useState(280);
  const isDragging = useRef(false);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    isDragging.current = true;
    const startX = e.clientX;
    const startW = leftWidth;
    const onMove = (ev: MouseEvent) => {
      if (!isDragging.current) return;
      const next = Math.min(520, Math.max(180, startW + ev.clientX - startX));
      setLeftWidth(next);
    };
    const onUp = () => {
      isDragging.current = false;
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
  }, [leftWidth]);

  // ── Render ──

  if (allNodes === null) {
    return <div className="root-loading">Loading catalogue…</div>;
  }

  return (
    <div className="app-root">
      <nav className="app-topbar">
        <span className="app-brand">Astra</span>
        <div className="app-tabs">
          <button
            className={"app-tab" + (mode === "navigate" ? " is-active" : "")}
            onClick={() => handleModeChange("navigate")}
          >
            NAVIGATE
          </button>
          <button
            className={"app-tab" + (mode === "consult" ? " is-active" : "")}
            onClick={() => handleModeChange("consult")}
          >
            CONSULT
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
            className={"app-tab" + (mode === "admin" ? " is-active" : "")}
            style={{
              background: mode === "admin" ? "rgba(255,255,255,0.18)" : "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.2)",
              display: "flex",
              alignItems: "center",
              gap: "0.4rem",
            }}
            onClick={() => handleModeChange("admin")}
          >
            <span style={{ fontSize: "1rem" }}>⚙</span>
            ADMIN
          </button>
        </div>
      </nav>

      {rootError && (
        <div className="root-error-banner">
          ⚠ API unavailable — {rootError}. Navigate shows catalog only.
        </div>
      )}

      {mode === "consult" && (
        <div className="app-grid" style={{ gridTemplateColumns: `${leftWidth}px 1fr 280px` }}>
          <div style={{ position: "relative", height: "100%", overflow: "hidden" }}>
            <TreePanel
              availableTypes={availableTypes}
              activeTypes={activeTypes}
              onToggleType={handleToggleType}
              tree={tree}
              selectedNodeId={selected?.node_id ?? null}
              onSelect={setSelected}
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
              documents={documents}
              selectedSource={selectedSource}
              onSelectSource={handleSelectSource}
              catalog={catalog}
            />
            <div className="resize-handle" onMouseDown={onDragStart} />
          </div>
          <ArticlePanel
            node={detail}
            loading={detailLoading}
            error={detailError}
            onNavigate={handleNavigateByRef}
            knownRefs={knownRefs}
            siblings={articleSiblings}
            onSelectSibling={setSelected}
            catalogEntry={catalog.find((e) => e.source_root === selectedSource) ?? null}
            versionCheck={versionChecks.find((v) => v.source_root === selectedSource) ?? null}
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
      {mode === "navigate" && (
        <NavigatePanel
          catalog={catalog}
          versionChecks={versionChecks}
          availableSources={new Set(documents.map((d) => d.source))}
          onNavigateTo={handleNavigateToSource}
        />
      )}
      {mode === "map" && (
        <MapPanel
          graphData={graphData}
          selectedNodeId={selected?.node_id ?? null}
          onNavigate={handleNavigateById}
        />
      )}

      {mode === "admin" && (
        <AdminConsole onClose={() => setMode("navigate")} />
      )}
    </div>
  );
}
