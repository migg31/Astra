import type { NodeSummary } from "../types";
import type { SubpartGroup } from "../tree";

interface Props {
  tree: SubpartGroup[];
  selectedNodeId: string | null;
  onSelect: (node: NodeSummary) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
}

export function TreePanel({ tree, selectedNodeId, onSelect, searchQuery, onSearchChange }: Props) {
  const isSearching = searchQuery.trim().length > 0;

  return (
    <nav className="tree-panel">
      <h2>Part 21 — Subparts B &amp; D</h2>
      <div className="tree-search">
        <input
          type="search"
          placeholder="Search…"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="tree-search-input"
        />
      </div>
      {isSearching ? (
        // Flat list when searching
        <ul className="tree-search-results">
          {tree.flatMap((subpart) =>
            subpart.articles.flatMap((article) =>
              article.nodes.map((node) => (
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
                    <strong>{node.reference_code}</strong>
                    {node.title ? ` — ${node.title}` : ""}
                  </span>
                </li>
              ))
            )
          )}
        </ul>
      ) : (
        // Normal tree
        tree.map((subpart) => (
          <section key={subpart.name} className="tree-subpart">
            <h3>{subpart.name}</h3>
            <ul>
              {subpart.articles.map((article) => (
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
          </section>
        ))
      )}
    </nav>
  );
}
