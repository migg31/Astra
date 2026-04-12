import { useEffect, useMemo, useState } from "react";
import type { DocumentInfo, NodeSummary, NodeType } from "../types";
import type { SubpartGroup } from "../tree";

interface Props {
  documents: DocumentInfo[];
  selectedSource: string | null;
  onSelectSource: (source: string) => void;
  /** Types present in the selected document — provided by App so pills never vanish on deselect. */
  availableTypes: NodeType[];
  activeTypes: Set<NodeType>;
  onToggleType: (type: NodeType) => void;
  tree: SubpartGroup[];
  selectedNodeId: string | null;
  onSelect: (node: NodeSummary) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
}

export function TreePanel({
  documents,
  selectedSource,
  onSelectSource,
  availableTypes,
  activeTypes,
  onToggleType,
  tree,
  selectedNodeId,
  onSelect,
  searchQuery,
  onSearchChange,
}: Props) {
  const isSearching = searchQuery.trim().length > 0;

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

  return (
    <nav className="tree-panel">
      {/* ── Document selector ── */}
      {documents.length > 0 && (
        <div className="tree-doc-list">
          <div className="tree-section-label">Documents</div>
          {documents.map((doc) => (
            <button
              key={doc.source}
              className={`tree-doc-item${doc.source === selectedSource ? " is-active" : ""}`}
              onClick={() => onSelectSource(doc.source)}
              title={doc.source}
            >
              <span className="tree-doc-label">{doc.label}</span>
              <span className="tree-doc-count">{doc.nodeCount}</span>
            </button>
          ))}
        </div>
      )}

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
        <div className="tree-scroll-area">
          {tree.map((subpart) => {
            const subpartKey = subpart.name;
            const isSubpartCollapsed = collapsed.has(subpartKey);
            const leafCount = subpart.articles.reduce((n, a) => n + a.nodes.length, 0);
            return (
              <section key={subpartKey} className="tree-subpart">
                <h3
                  className="tree-subpart-header"
                  onClick={() => toggle(subpartKey)}
                  title={isSubpartCollapsed ? "Expand" : "Collapse"}
                >
                  <span className="tree-subpart-chevron">{isSubpartCollapsed ? "▶" : "▼"}</span>
                  <span className="tree-subpart-name">{subpart.name}</span>
                  <span className="tree-subpart-count">{leafCount}</span>
                </h3>
                {!isSubpartCollapsed && (
                  <div>
                    {subpart.sections.map((section) => {
                      const sectionKey = `${subpartKey}::${section.name}`;
                      const isSectionCollapsed = collapsed.has(sectionKey);
                      const sectionLeafCount = section.articles.reduce((n, a) => n + a.nodes.length, 0);
                      return (
                        <div key={sectionKey} className="tree-section">
                          {/* Only render section header when it has a name */}
                          {section.name && (
                            <h4
                              className="tree-section-header"
                              onClick={() => toggle(sectionKey)}
                              title={isSectionCollapsed ? "Expand" : "Collapse"}
                            >
                              <span className="tree-subpart-chevron">{isSectionCollapsed ? "▶" : "▼"}</span>
                              <span className="tree-section-name">{section.name}</span>
                              <span className="tree-subpart-count">{sectionLeafCount}</span>
                            </h4>
                          )}
                          {!isSectionCollapsed && (
                            <ul>
                              {section.articles.map((article) => (
                                <li key={article.articleCode}>
                                  <div className="tree-article-code">{article.articleCode}</div>
                                  <ul className="tree-variants">
                                    {article.nodes.map((node) => (
                                      <li
                                        key={node.node_id}
                                        className={
                                          "tree-leaf" +
                                          (node.node_id === selectedNodeId ? " is-selected" : "")
                                        }
                                        onClick={() => onSelect(node)}
                                      >
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
    </nav>
  );
}
