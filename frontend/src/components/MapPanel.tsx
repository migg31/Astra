import * as d3 from "d3";
import { useEffect, useRef, useState } from "react";
import { getNode } from "../api";
import type { GraphData, GraphNode, NodeDetail } from "../types";

interface Props {
  graphData: GraphData | null;
  selectedNodeId: string | null;
  onNavigate: (nodeId: string) => void;
}

// ---- Visual constants ----

const NODE_COLORS: Record<string, string> = {
  IR:    "#007FC2",
  AMC:   "#FBBC39",
  GM:    "#16CC7F",
  CS:    "#A25EAB",
  GROUP: "#e2e8f0",
};

const GROUP_STROKE = "#222F64";

const RELATION_COLORS: Record<string, string> = {
  ACCEPTABLE_MEANS: "#FBBC39",
  GUIDANCE_FOR:     "#16CC7F",
  IMPLEMENTS:       "#007FC2",
  REQUIRES:         "#007FC2",
  REFERENCES:       "#94a3b8",
  EQUIVALENT_TO:    "#f97316",
  SUPERSEDES:       "#ea580c",
  IF_MINOR:         "#0ea5e9",
  IF_MAJOR:         "#0284c7",
  LEADS_TO:         "#0369a1",
  CONTAINS:         "transparent",
};

const CONTENT_TYPES = ["IR", "AMC", "GM", "CS"] as const;
const NODE_R  = 7;
const IR_R    = 10;
const GROUP_R = 22;

// ---- D3 types ----

interface SimNode extends d3.SimulationNodeDatum {
  node_id:        string;
  node_type:      string;
  reference_code: string;
  title:          string | null;
}

interface SimLink extends d3.SimulationLinkDatum<SimNode> {
  relation: string;
}

function nodeRadius(d: SimNode): number {
  if (d.node_type === "GROUP") return GROUP_R;
  if (d.node_type === "IR")    return IR_R;
  return NODE_R;
}

function shortLabel(refCode: string): string {
  const m = refCode.match(/^Appendix\s+([A-Z0-9]+)/i);
  if (m) return `App ${m[1]}`;
  return refCode;
}

// ---- Component ----

export function MapPanel({ graphData, selectedNodeId, onNavigate }: Props) {
  const svgRef     = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const simRef     = useRef<d3.Simulation<SimNode, SimLink> | null>(null);
  const collapsedRef      = useRef<Set<string>>(new Set());
  const currentTransformRef = useRef(d3.zoomIdentity);

  // D3 selection refs — shared between the build effect and filter/collapse effects
  const nodeSelRef  = useRef<d3.Selection<SVGCircleElement, SimNode, SVGGElement, unknown> | null>(null);
  const edgeSelRef  = useRef<d3.Selection<SVGLineElement,   SimLink,  SVGGElement, unknown> | null>(null);
  const labelSelRef = useRef<d3.Selection<SVGTextElement,   SimNode,  SVGGElement, unknown> | null>(null);

  // groupChildren: groupId → Set<childId>
  const groupChildrenRef = useRef<Map<string, Set<string>>>(new Map());
  // containsMap: childId → groupId
  const containsMapRef   = useRef<Map<string, string>>(new Map());

  // React state
  const [visibleTypes, setVisibleTypes]   = useState<Set<string>>(new Set(CONTENT_TYPES));
  const [detailNode,   setDetailNode]     = useState<GraphNode | null>(null);
  const [nodeDetail,   setNodeDetail]     = useState<NodeDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  // ---- Build D3 graph ----
  useEffect(() => {
    if (!graphData || !svgRef.current) return;
    simRef.current?.stop();

    const svgEl  = svgRef.current;
    const width  = svgEl.clientWidth  || 1200;
    const height = svgEl.clientHeight || 700;
    const svg    = d3.select(svgEl);
    svg.selectAll("*").remove();
    collapsedRef.current.clear();

    const nodes: SimNode[] = graphData.nodes.map((n) => ({
      node_id: n.node_id, node_type: n.node_type,
      reference_code: n.reference_code, title: n.title,
    }));
    const nodeById = new Map(nodes.map((n) => [n.node_id, n]));

    const groups = nodes.filter((n) => n.node_type === "GROUP");
    const R = Math.min(width, height) * 0.35;
    groups.forEach((g, i) => {
      const angle = (2 * Math.PI * i) / groups.length - Math.PI / 2;
      g.x = width  / 2 + R * Math.cos(angle);
      g.y = height / 2 + R * Math.sin(angle);
    });

    const containsMap = new Map<string, string>();
    const groupChildren = new Map<string, Set<string>>();
    graphData.edges.filter((e) => e.relation === "CONTAINS").forEach((e) => {
      containsMap.set(e.target_node_id, e.source_node_id);
      if (!groupChildren.has(e.source_node_id)) groupChildren.set(e.source_node_id, new Set());
      groupChildren.get(e.source_node_id)!.add(e.target_node_id);
    });
    containsMapRef.current   = containsMap;
    groupChildrenRef.current = groupChildren;

    nodes.filter((n) => n.node_type !== "GROUP").forEach((n) => {
      const gId = containsMap.get(n.node_id);
      const parent = gId ? nodeById.get(gId) : null;
      if (parent?.x != null && parent?.y != null) {
        n.x = parent.x + (Math.random() - 0.5) * 80;
        n.y = parent.y + (Math.random() - 0.5) * 80;
      } else {
        n.x = width  / 2 + (Math.random() - 0.5) * 200;
        n.y = height / 2 + (Math.random() - 0.5) * 200;
      }
    });

    const links: SimLink[] = graphData.edges.flatMap((e) => {
      const s = nodeById.get(e.source_node_id);
      const t = nodeById.get(e.target_node_id);
      if (!s || !t) return [];
      return [{ source: s, target: t, relation: e.relation }];
    });

    const sim = d3.forceSimulation<SimNode>(nodes)
      .force("link", d3.forceLink<SimNode, SimLink>(links)
        .id((d) => d.node_id)
        .distance((l) => l.relation === "CONTAINS" ? 70 : 55)
        .strength((l) => l.relation === "CONTAINS" ? 0.8 : 0.2))
      .force("charge", d3.forceManyBody<SimNode>().strength(-150))
      .force("collide", d3.forceCollide<SimNode>((d) => nodeRadius(d) + 4));

    groups.forEach((g) => { g.fx = g.x; g.fy = g.y; });
    simRef.current = sim;

    const defs = svg.append("defs");
    const arrowColors = [...new Set(
      Object.entries(RELATION_COLORS)
        .filter(([k]) => k !== "CONTAINS")
        .map(([, v]) => v)
    )];
    arrowColors.forEach((color) => {
      defs.append("marker")
        .attr("id", `arrow-${color.slice(1)}`)
        .attr("viewBox", "0 -4 8 8")
        .attr("refX", 18).attr("refY", 0)
        .attr("markerWidth", 5).attr("markerHeight", 5)
        .attr("orient", "auto")
        .append("path").attr("d", "M0,-4L8,0L0,4").attr("fill", color);
    });

    const g               = svg.append("g").attr("class", "map-root");
    const edgeLayer       = g.append("g").attr("class", "map-edge-layer");
    const nodeLayer       = g.append("g").attr("class", "map-node-layer");
    const labelLayer      = g.append("g").attr("class", "map-label-layer");
    const groupLabelLayer = g.append("g").attr("class", "map-group-label-layer");

    const regulatoryLinks = links.filter((l) => l.relation !== "CONTAINS");
    const edgeSel = edgeLayer.selectAll<SVGLineElement, SimLink>("line")
      .data(regulatoryLinks)
      .join("line")
      .attr("class", "map-edge")
      .attr("stroke", (d) => RELATION_COLORS[d.relation] ?? "#94a3b8")
      .attr("stroke-width", 1.5)
      .attr("marker-end", (d) => {
        const c = RELATION_COLORS[d.relation] ?? "#94a3b8";
        return `url(#arrow-${c.slice(1)})`;
      })
      .style("opacity", 0);
    edgeSelRef.current = edgeSel;

    const nodeSel = nodeLayer.selectAll<SVGCircleElement, SimNode>("circle")
      .data(nodes)
      .join("circle")
      .attr("class", (d) => {
        const cls = ["map-node"];
        if (d.node_type === "GROUP") cls.push("map-group-node");
        if (d.node_id === selectedNodeId) cls.push("is-selected");
        return cls.join(" ");
      })
      .attr("r",           (d) => nodeRadius(d))
      .attr("fill",        (d) => NODE_COLORS[d.node_type] ?? "#94a3b8")
      .attr("stroke",      (d) => d.node_type === "GROUP" ? GROUP_STROKE : "rgba(0,0,0,0.18)")
      .attr("stroke-width",(d) => d.node_type === "GROUP" ? 2 : 1)
      .style("cursor", "grab")
      .on("dblclick", (_event, d: SimNode) => {
        if (d.node_type !== "GROUP") { d.fx = null; d.fy = null; sim.alphaTarget(0.3).restart(); }
      })
      .on("mouseover", (event: MouseEvent, d) => showTooltip(event, d))
      .on("mousemove", (event: MouseEvent) => moveTooltip(event))
      .on("mouseout", () => hideTooltip());
    nodeSelRef.current = nodeSel;

    // ---- D3 drag (correct coords via nodeLayer container) ----
    let dragDist = 0;
    const dragBehavior = d3.drag<SVGCircleElement, SimNode>()
      .container(() => nodeLayer.node() as SVGGElement)
      .on("start", function(event, d) {
        event.sourceEvent.stopPropagation();   // prevent zoom from starting
        dragDist = 0;
        if (!event.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x ?? 0; d.fy = d.y ?? 0;
        d3.select(this).style("cursor", "grabbing");
      })
      .on("drag", function(_event, d) {
        dragDist += Math.sqrt(_event.dx * _event.dx + _event.dy * _event.dy);
        d.fx = _event.x; d.fy = _event.y;
      })
      .on("end", function(event, d) {
        if (!event.active) sim.alphaTarget(0);
        d3.select(this).style("cursor", "grab");
        // Treat as click if barely moved
        if (dragDist < 4) {
          if (d.node_type === "GROUP") {
            toggleCollapse(d.node_id);
          } else {
            const gNode = graphData.nodes.find((n) => n.node_id === d.node_id) ?? null;
            setDetailNode(gNode);
          }
        }
        // Keep node pinned at drop position (don't null fx/fy)
      });
    nodeSel.call(dragBehavior as unknown as (sel: typeof nodeSel) => void);

    const contentNodes = nodes.filter((n) => n.node_type !== "GROUP");
    const labelSel = labelLayer.selectAll<SVGTextElement, SimNode>("text")
      .data(contentNodes)
      .join("text")
      .attr("class", "map-label")
      .attr("dy", (d) => nodeRadius(d) + 11)
      .text((d) => shortLabel(d.reference_code))
      .style("opacity", 0);
    labelSelRef.current = labelSel;

    groupLabelLayer.selectAll<SVGTextElement, SimNode>("text")
      .data(groups)
      .join("text")
      .attr("class", "map-group-label")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "central")
      .text((d) => d.reference_code.replace("SUBPART ", "SP "))
      .style("pointer-events", "none");

    // ---- Collapse/expand ----
    function toggleCollapse(groupId: string) {
      if (collapsedRef.current.has(groupId)) collapsedRef.current.delete(groupId);
      else collapsedRef.current.add(groupId);
      applyVisibility();
    }

    // ---- LOD ----
    let currentK = 0.9;
    function applyLOD(k: number) {
      currentK = k;
      applyVisibility();
    }

    // ---- Combined visibility (collapse + filter + LOD) ----
    function applyVisibility() {
      const hidden = getHiddenIds();
      // Read current visibleTypes from DOM data attribute (set by React)
      const visAttr = svgEl.dataset.visibleTypes ?? CONTENT_TYPES.join(",");
      const vis = new Set(visAttr.split(","));

      nodeSelRef.current
        ?.style("opacity", (d) => {
          if (d.node_type === "GROUP") return null;
          if (!vis.has(d.node_type)) return 0;
          return hidden.has(d.node_id) ? 0 : null;
        })
        .style("pointer-events", (d) => {
          if (d.node_type === "GROUP") return null;
          if (!vis.has(d.node_type)) return "none";
          return hidden.has(d.node_id) ? "none" : null;
        });

      // GROUP dashed border when collapsed
      nodeSelRef.current?.filter((d) => d.node_type === "GROUP")
        .attr("stroke-dasharray", (d) => collapsedRef.current.has(d.node_id) ? "5,3" : null);

      edgeSelRef.current?.style("opacity", (d) => {
        const src = (d.source as SimNode);
        const tgt = (d.target as SimNode);
        if (!vis.has(src.node_type) || !vis.has(tgt.node_type)) return 0;
        if (hidden.has(src.node_id) || hidden.has(tgt.node_id)) return 0;
        return currentK < 1.2 ? 0 : 0.65;
      });

      labelSelRef.current?.style("opacity", (d) => {
        if (!vis.has(d.node_type)) return 0;
        if (hidden.has(d.node_id)) return 0;
        return currentK < 1.5 ? 0 : 1;
      });
    }

    function getHiddenIds(): Set<string> {
      const s = new Set<string>();
      collapsedRef.current.forEach((gId) => {
        groupChildrenRef.current.get(gId)?.forEach((cId) => s.add(cId));
      });
      return s;
    }

    // ---- Zoom ----
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.12, 6])
      .on("zoom", ({ transform }) => {
        currentTransformRef.current = transform;
        g.attr("transform", transform.toString());
        applyLOD(transform.k);
      });
    svg.call(zoom);
    const initTransform = d3.zoomIdentity.translate(width * 0.05, height * 0.05).scale(0.9);
    svg.call(zoom.transform, initTransform);
    currentTransformRef.current = initTransform;

    // ---- Tick ----
    sim.on("tick", () => {
      edgeSel
        .attr("x1", (d) => (d.source as SimNode).x ?? 0)
        .attr("y1", (d) => (d.source as SimNode).y ?? 0)
        .attr("x2", (d) => (d.target as SimNode).x ?? 0)
        .attr("y2", (d) => (d.target as SimNode).y ?? 0);

      nodeSel.attr("cx", (d) => d.x ?? 0).attr("cy", (d) => d.y ?? 0);
      labelSel.attr("x", (d) => d.x ?? 0).attr("y", (d) => d.y ?? 0);

      groupLabelLayer.selectAll<SVGTextElement, SimNode>("text")
        .attr("x", (d) => d.x ?? 0)
        .attr("y", (d) => d.y ?? 0);
    });

    applyLOD(0.9);

    return () => { sim.stop(); };
  }, [graphData]); // eslint-disable-line react-hooks/exhaustive-deps

  // ---- Sync visibleTypes → D3 via data attribute ----
  useEffect(() => {
    if (!svgRef.current) return;
    svgRef.current.dataset.visibleTypes = [...visibleTypes].join(",");
    // Trigger a re-application of visibility via a minimal re-select
    const svg = d3.select(svgRef.current);
    const vis = visibleTypes;
    svg.selectAll<SVGCircleElement, SimNode>(".map-node")
      .style("opacity", (d) => {
        if (d.node_type === "GROUP") return null;
        return vis.has(d.node_type) ? null : 0;
      })
      .style("pointer-events", (d) => {
        if (d.node_type === "GROUP") return null;
        return vis.has(d.node_type) ? null : "none";
      });
    svg.selectAll<SVGTextElement, SimNode>(".map-label")
      .style("opacity", (d) => vis.has(d.node_type) ? null : 0);
    svg.selectAll<SVGLineElement, SimLink>(".map-edge")
      .style("opacity", (d) => {
        const src = d.source as SimNode;
        const tgt = d.target as SimNode;
        if (!vis.has(src.node_type) || !vis.has(tgt.node_type)) return 0;
        return null;
      });
  }, [visibleTypes]);

  // ---- Sync selected node highlight ----
  useEffect(() => {
    if (!svgRef.current) return;
    d3.select(svgRef.current)
      .selectAll<SVGCircleElement, SimNode>(".map-node")
      .classed("is-selected", (d) => d.node_id === selectedNodeId);
  }, [selectedNodeId]);

  // ---- Fetch node detail when detail panel opens ----
  useEffect(() => {
    if (!detailNode) { setNodeDetail(null); return; }
    setDetailLoading(true);
    setNodeDetail(null);
    getNode(detailNode.node_id)
      .then(setNodeDetail)
      .catch(console.error)
      .finally(() => setDetailLoading(false));
  }, [detailNode]);

  // ---- Tooltip ----
  function showTooltip(event: MouseEvent, d: SimNode) {
    if (!tooltipRef.current) return;
    const isGroup = d.node_type === "GROUP";
    tooltipRef.current.innerHTML = isGroup
      ? `<strong>${d.reference_code}</strong><br/><span>Click to collapse/expand</span>`
      : `<strong>${d.reference_code}</strong>${d.title ? `<br/><span>${d.title}</span>` : ""}`;
    tooltipRef.current.style.display = "block";
    moveTooltip(event);
  }
  function moveTooltip(event: MouseEvent) {
    if (!tooltipRef.current) return;
    tooltipRef.current.style.left = `${event.clientX + 14}px`;
    tooltipRef.current.style.top  = `${event.clientY - 10}px`;
  }
  function hideTooltip() {
    if (tooltipRef.current) tooltipRef.current.style.display = "none";
  }

  function toggleType(type: string) {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      next.has(type) ? next.delete(type) : next.add(type);
      return next;
    });
  }

  if (!graphData) return <div className="map-loading">Loading graph…</div>;

  return (
    <div className="map-container">
      {/* Filter bar */}
      <div className="map-filter-bar">
        {CONTENT_TYPES.map((type) => (
          <label key={type} className="map-filter-item">
            <input
              type="checkbox"
              checked={visibleTypes.has(type)}
              onChange={() => toggleType(type)}
            />
            <span className={`badge badge-${type}`}>{type}</span>
          </label>
        ))}
      </div>

      {/* Graph */}
      <svg ref={svgRef} className="map-svg" />
      <div ref={tooltipRef} className="map-tooltip" style={{ display: "none" }} />

      {/* Node detail panel */}
      {detailNode && detailNode.node_type !== "GROUP" && (
        <div className="map-detail-panel">
          <div className="map-detail-header">
            <span className={`badge badge-${detailNode.node_type}`}>{detailNode.node_type}</span>
            <button className="map-detail-close" onClick={() => setDetailNode(null)}>✕</button>
          </div>
          <div className="map-detail-ref">{detailNode.reference_code}</div>
          {detailNode.title && <div className="map-detail-title">{detailNode.title}</div>}
          <div className="map-detail-path">{detailNode.hierarchy_path}</div>

          <button
            className="map-detail-explore-btn"
            onClick={() => { onNavigate(detailNode.node_id); setDetailNode(null); }}
          >
            Open in EXPLORE →
          </button>

          <div className="map-detail-content">
            {detailLoading && <div className="map-detail-loading">Loading…</div>}
            {nodeDetail && (
              nodeDetail.content_html
                ? <div
                    className="article-html"
                    dangerouslySetInnerHTML={{ __html: nodeDetail.content_html }}
                  />
                : <pre className="map-detail-text">{nodeDetail.content_text}</pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
