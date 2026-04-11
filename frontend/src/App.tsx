import { useEffect, useMemo, useState } from "react";
import { getNeighbors, getNode, listAllNodes } from "./api";
import { ArticlePanel } from "./components/ArticlePanel";
import { NeighborsPanel } from "./components/NeighborsPanel";
import { TreePanel } from "./components/TreePanel";
import { buildTree } from "./tree";
import type {
  NeighborsResponse,
  NodeDetail,
  NodeSummary,
} from "./types";

export default function App() {
  const [allNodes, setAllNodes] = useState<NodeSummary[] | null>(null);
  const [rootError, setRootError] = useState<string | null>(null);

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

  const tree = useMemo(() => (allNodes ? buildTree(allNodes) : []), [allNodes]);

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
    <div className="app-grid">
      <TreePanel
        tree={tree}
        selectedNodeId={selected?.node_id ?? null}
        onSelect={setSelected}
      />
      <ArticlePanel node={detail} loading={detailLoading} error={detailError} />
      <NeighborsPanel
        neighbors={neighbors}
        loading={detailLoading}
        onSelect={setSelected}
      />
    </div>
  );
}
