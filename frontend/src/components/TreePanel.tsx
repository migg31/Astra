import type { NodeSummary } from "../types";
import type { SubpartGroup } from "../tree";

interface Props {
  tree: SubpartGroup[];
  selectedNodeId: string | null;
  onSelect: (node: NodeSummary) => void;
}

export function TreePanel({ tree, selectedNodeId, onSelect }: Props) {
  return (
    <nav className="tree-panel">
      <h2>Part 21 — Subparts B &amp; D</h2>
      {tree.map((subpart) => (
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
      ))}
    </nav>
  );
}
