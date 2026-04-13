import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, ChevronDown, FolderOpen, Folder, BookOpen, FileText, Clock } from "lucide-react";
import type { CatalogEntry } from "../api";
import type { DocumentInfo, NodeSummary, NodeType } from "../types";
import type { SubpartGroup } from "../tree";
import { DocumentHistoryPanel } from "./DocumentHistoryPanel";

// ─── Domain palette (same as NavigatePanel) ───────────────────
const DOMAIN_META: Record<string, { bg: string; text: string; border: string; label: string }> = {
  "framework":                { bg: "#1e293b", text: "#f1f5f9",  border: "#334155", label: "Framework" },
  "initial-airworthiness":    { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Initial Airworthiness" },
  "avionics":                 { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Initial Airworthiness" },
  "continuing-airworthiness": { bg: "#1e3a8a", text: "#dbeafe",  border: "#2563eb", label: "Continuing Airworthiness" },
  "air-operations":           { bg: "#4c1d95", text: "#e9d5ff",  border: "#7c3aed", label: "Air Operations" },
  "aircrew":                  { bg: "#0c4a6e", text: "#bae6fd",  border: "#0284c7", label: "Aircrew" },
  "aerodromes":               { bg: "#134e4a", text: "#99f6e4",  border: "#14b8a6", label: "Aerodromes" },
};
const DOMAIN_ORDER = ["framework","initial-airworthiness","continuing-airworthiness","air-operations","aircrew","aerodromes"];
function domainMeta(d: string) { return DOMAIN_META[d] ?? DOMAIN_META["framework"]; }

// ─── DocPicker component ──────────────────────────────────────
interface PickerProps {
  catalog: CatalogEntry[];
  documents: DocumentInfo[];
  selectedSource: string | null;
  onSelectSource: (source: string) => void;
  onShowHistory: (() => void) | null;
}
function DocPicker({ catalog, documents, selectedSource, onSelectSource, onShowHistory }: PickerProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handle = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  const activeEntry = catalog.find((e) => e.source_root === selectedSource);
  const activeMeta = activeEntry ? domainMeta(activeEntry.domain) : domainMeta("framework");
  const activeDoc = documents.find((d) => d.source === selectedSource);

  // Group catalog by canonical domain
  const byDomain = new Map<string, CatalogEntry[]>();
  for (const e of catalog) {
    const key = e.domain === "avionics" ? "initial-airworthiness" : e.domain;
    if (!byDomain.has(key)) byDomain.set(key, []);
    byDomain.get(key)!.push(e);
  }
  const docByRoot = new Map(documents.map((d) => [d.source, d]));

  return (
    <div className="dp-wrapper" ref={ref}>
      {/* Trigger */}
      <button
        className="dp-trigger"
        style={{ borderColor: activeMeta.border, background: activeMeta.bg, color: activeMeta.text }}
        onClick={() => setOpen(!open)}
      >
        <span className="dp-trigger-dot" style={{ background: activeMeta.text }} />
        <span className="dp-trigger-label">
          {activeEntry?.short ?? activeDoc?.label ?? "Select document"}
        </span>
        <span className="dp-trigger-count">
          {activeDoc?.nodeCount ?? ""}
        </span>
        <span className="dp-trigger-chevron">{open ? "▲" : "▼"}</span>
        {onShowHistory && (
          <span
            className="dp-trigger-history"
            title="Historique des versions"
            onClick={(e) => { e.stopPropagation(); onShowHistory(); }}
          >📋</span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="dp-dropdown">
          <div className="dp-dropdown-title">EASA Regulatory Framework</div>
          <div className="dp-dropdown-body">
            {DOMAIN_ORDER.filter((dk) => byDomain.has(dk)).map((dk) => {
              const meta = domainMeta(dk);
              const entries = byDomain.get(dk)!;
              return (
                <div key={dk} className="dp-domain">
                  <div className="dp-domain-header" style={{ background: meta.bg, color: meta.text }}>
                    {meta.label}
                  </div>
                  {entries.map((entry) => {
                    const doc = entry.source_root ? docByRoot.get(entry.source_root) : null;
                    const isActive = entry.source_root === selectedSource;
                    return (
                      <button
                        key={entry.id}
                        className={"dp-item" + (isActive ? " is-active" : "") + (!entry.indexed ? " is-unindexed" : "")}
                        style={isActive ? { borderLeftColor: meta.border } : {}}
                        onClick={() => { if (entry.source_root && doc) { onSelectSource(entry.source_root); setOpen(false); } }}
                        disabled={!entry.indexed || !entry.source_root}
                        title={!entry.indexed ? "Not indexed" : entry.name}
                      >
                        <span className="dp-item-short" style={isActive ? { color: meta.border } : {}}>
                          {entry.short}
                        </span>
                        <span className="dp-item-name">
                          {entry.name.replace(/^[^\u2014]+\u2014\s*/, "")}
                        </span>
                        {entry.indexed && doc
                          ? <span className="dp-item-count">{doc.nodeCount}</span>
                          : <span className="dp-item-na">—</span>
                        }
                      </button>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

interface Props {
  /** Types present in the selected document — provided by App so pills never vanish on deselect. */
  availableTypes: NodeType[];
  activeTypes: Set<NodeType>;
  onToggleType: (type: NodeType) => void;
  tree: SubpartGroup[];
  selectedNodeId: string | null;
  onSelect: (node: NodeSummary) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  // DocPicker props
  catalog: CatalogEntry[];
  documents: DocumentInfo[];
  selectedSource: string | null;
  onSelectSource: (source: string) => void;
  // Auto-expand + scroll to a specific node
  scrollToNodeId?: string | null;
  onScrolled?: () => void;
}

export function TreePanel({
  availableTypes,
  activeTypes,
  onToggleType,
  tree,
  selectedNodeId,
  onSelect,
  searchQuery,
  onSearchChange,
  catalog,
  documents,
  selectedSource,
  onSelectSource,
  scrollToNodeId,
  onScrolled,
}: Props) {
  const isSearching = searchQuery.trim().length > 0;
  const [showHistory, setShowHistory] = useState(false);
  const scrollAreaRef = useRef<HTMLDivElement>(null);

  // Derive source_key from catalog for the selected source
  const activeEntry = catalog.find((e) => e.source_root === selectedSource);
  const historySourceKey = activeEntry?.harvest_key ?? null;

  // Compute all collapsible keys from the current tree
  const allKeys = useMemo(() => {
    const keys: string[] = [];
    for (const subpart of tree) {
      keys.push(subpart.name);
      for (const section of subpart.sections) {
        if (section.name) keys.push(`${subpart.name}::${section.name}`);
      }
    }
    return keys;
  }, [tree]);

  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set(allKeys));

  // Collapse everything whenever the document changes (tree rebuilt)
  useEffect(() => {
    setCollapsed(new Set(allKeys));
  }, [allKeys]);

  function toggle(key: string) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  // Auto-expand + scroll when scrollToNodeId is set
  useEffect(() => {
    if (!scrollToNodeId) return;
    // Find which subpart+section contains this node
    const keysToExpand: string[] = [];
    for (const subpart of tree) {
      const subpartKey = subpart.name;
      for (const section of subpart.sections) {
        const sectionKey = section.name ? `${subpartKey}::${section.name}` : null;
        const allArticles = [...subpart.articles, ...section.articles];
        const found = allArticles.some((art) =>
          art.nodes.some((n) => n.node_id === scrollToNodeId)
        );
        if (found) {
          keysToExpand.push(subpartKey);
          if (sectionKey) keysToExpand.push(sectionKey);
          break;
        }
      }
    }
    if (keysToExpand.length > 0) {
      setCollapsed((prev) => {
        const next = new Set(prev);
        keysToExpand.forEach((k) => next.delete(k));
        return next;
      });
    }
    // Scroll after a tick so the DOM is updated
    setTimeout(() => {
      const el = scrollAreaRef.current?.querySelector(`[data-nodeid="${scrollToNodeId}"]`) as HTMLElement | null;
      el?.scrollIntoView({ behavior: "smooth", block: "center" });
      onScrolled?.();
    }, 80);
  }, [scrollToNodeId]);

  return (
    <nav className="tree-panel">

      {/* ── DocPicker ── */}
      <DocPicker
        catalog={catalog}
        documents={documents}
        selectedSource={selectedSource}
        onSelectSource={onSelectSource}
        onShowHistory={null}
      />

      {/* ── Type filters ── */}
      {availableTypes.length > 1 && (
        <div className="tree-type-filters">
          {availableTypes.map((t) => (
            <button
              key={t}
              className={`tree-type-pill pill-${t}${activeTypes.has(t) ? " is-active" : ""}`}
              onClick={() => onToggleType(t)}
            >
              {t}
            </button>
          ))}
        </div>
      )}

      {/* ── Search ── */}
      <div className="tree-search">
        <input
          type="search"
          placeholder="Search…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="tree-search-input"
        />
      </div>

      {/* ── Tree ── */}
      {isSearching ? (
        <ul className="tree-search-results">
          {tree.flatMap((subpart) =>
            subpart.articles.flatMap((article) =>
              article.nodes.map((node) => (
                <li
                  key={node.node_id}
                  className={"tree-leaf" + (node.node_id === selectedNodeId ? " is-selected" : "")}
                  onClick={() => onSelect(node)}
                >
                  <span className={`badge badge-${node.node_type}`}>{node.node_type}</span>
                  <span className="tree-leaf-title">
                    <strong>{node.reference_code}</strong>
                    {node.title ? ` — ${node.title}` : ""}
                  </span>
                </li>
              ))
            )
          )}
        </ul>
      ) : (
        <div className="tree-scroll-area" ref={scrollAreaRef}>
          {tree.map((subpart) => {
            const subpartKey = subpart.name;
            const isSubpartCollapsed = collapsed.has(subpartKey);
            const leafCount = subpart.articles.reduce((n, a) => n + a.nodes.length, 0);
            const SubpartIcon = isSubpartCollapsed ? Folder : FolderOpen;
            return (
              <section key={subpartKey} className="tree-subpart">
                <h3
                  className="tree-subpart-header"
                  onClick={() => toggle(subpartKey)}
                  title={isSubpartCollapsed ? "Expand" : "Collapse"}
                >
                  <span className="tree-subpart-chevron">
                    {isSubpartCollapsed
                      ? <ChevronRight size={12} strokeWidth={2.5} />
                      : <ChevronDown size={12} strokeWidth={2.5} />}
                  </span>
                  <SubpartIcon size={13} strokeWidth={1.8} className="tree-subpart-icon" />
                  <span className="tree-subpart-name">{subpart.name}</span>
                  <span className="tree-subpart-count">{leafCount}</span>
                </h3>
                {!isSubpartCollapsed && (
                  <div className="tree-subpart-body">
                    {subpart.sections.map((section) => {
                      const sectionKey = `${subpartKey}::${section.name}`;
                      const isSectionCollapsed = collapsed.has(sectionKey);
                      const sectionLeafCount = section.articles.reduce((n, a) => n + a.nodes.length, 0);
                      return (
                        <div key={sectionKey} className="tree-section">
                          {section.name && (
                            <h4
                              className="tree-section-header"
                              onClick={() => toggle(sectionKey)}
                              title={isSectionCollapsed ? "Expand" : "Collapse"}
                            >
                              <span className="tree-subpart-chevron">
                                {isSectionCollapsed
                                  ? <ChevronRight size={11} strokeWidth={2.5} />
                                  : <ChevronDown size={11} strokeWidth={2.5} />}
                              </span>
                              <BookOpen size={11} strokeWidth={1.8} className="tree-section-icon" />
                              <span className="tree-section-name">{section.name}</span>
                              <span className="tree-subpart-count">{sectionLeafCount}</span>
                            </h4>
                          )}
                          {!isSectionCollapsed && (
                            <ul className="tree-articles-list">
                              {section.articles.map((article) => (
                                <li key={article.articleCode} className="tree-article-group">
                                  {article.articleCode && !article.articleCode.startsWith("§") && (
                                    <div className="tree-article-code">{article.articleCode}</div>
                                  )}
                                  {article.articleCode.startsWith("§") && (
                                    <div className="tree-article-code tree-article-synthetic">
                                      {article.articleCode.slice(1)}
                                    </div>
                                  )}
                                  <ul className="tree-variants">
                                    {article.nodes.map((node) => (
                                      <li
                                        key={node.node_id}
                                        data-nodeid={node.node_id}
                                        className={
                                          "tree-leaf" +
                                          (node.node_id === selectedNodeId ? " is-selected" : "")
                                        }
                                        onClick={() => onSelect(node)}
                                      >
                                        <FileText size={11} strokeWidth={1.8} className="tree-leaf-icon" />
                                        <span className={`badge badge-${node.node_type}`}>
                                          {node.node_type}
                                        </span>
                                        <span className="tree-leaf-title">
                                          {node.title ?? node.reference_code}
                                        </span>
                                      </li>
                                    ))}
                                  </ul>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {/* ── History drawer ── */}
      {historySourceKey && activeEntry && (
        <div className={`tree-history-drawer${showHistory ? " is-open" : ""}`}>
          <button
            className="tree-history-drawer-header"
            onClick={() => setShowHistory((v) => !v)}
          >
            <span className="tree-history-drawer-chevron">
              {showHistory ? <ChevronDown size={12} strokeWidth={2.5} /> : <ChevronRight size={12} strokeWidth={2.5} />}
            </span>
            <Clock size={12} strokeWidth={1.8} />
            <span className="tree-history-drawer-label">Version history</span>
          </button>
          {showHistory && (
            <div className="tree-history-drawer-body">
              <DocumentHistoryPanel
                sourceKey={historySourceKey}
                sourceLabel={activeEntry.name}
                onClose={() => setShowHistory(false)}
              />
            </div>
          )}
        </div>
      )}
    </nav>
  );
}
