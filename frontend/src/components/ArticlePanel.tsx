import { useEffect, useRef, useState } from "react";
import type { NodeDetail, NodeSummary, NodeType } from "../types";
import { typeOrder } from "../tree";

interface Props {
  node: NodeDetail | null;
  loading: boolean;
  error: string | null;
  onNavigate?: (refCode: string) => void;
  knownRefs?: Set<string>;
  /** All IR/AMC/GM nodes sharing the same article code (includes current node). */
  siblings?: NodeSummary[] | null;
  onSelectSibling?: (node: NodeSummary) => void;
}

// Matches any Part 21 article reference: 21.A.20, 21.B.80, 21.A.101A, etc.
const ANY_REF_RE = /21\.[A-Z]\.\d+[A-Z]?/g;

/**
 * Walk the real DOM text nodes inside `container` and wrap every article
 * reference with a <span>:
 *   - .crossref       if the ref exists in knownRefs (navigable, blue)
 *   - .crossref-external  otherwise (mentioned but not in our DB, gray)
 * The node's own reference code is left as plain text.
 */
function linkifyDom(
  container: HTMLElement,
  ownRef: string,
  knownRefs: Set<string>
) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const targets: Text[] = [];
  let tw: Node | null;
  while ((tw = walker.nextNode())) {
    const text = (tw as Text).textContent ?? "";
    ANY_REF_RE.lastIndex = 0;
    if (ANY_REF_RE.test(text)) targets.push(tw as Text);
  }

  for (const textNode of targets) {
    const text = textNode.textContent ?? "";
    const parent = textNode.parentNode as Element | null;
    if (!parent) continue;
    if (parent.classList?.contains("crossref") || parent.classList?.contains("crossref-external")) continue;

    const fragment = document.createDocumentFragment();
    let lastIndex = 0;
    ANY_REF_RE.lastIndex = 0;

    let match: RegExpExecArray | null;
    while ((match = ANY_REF_RE.exec(text)) !== null) {
      const ref = match[0];
      if (match.index > lastIndex) {
        fragment.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
      }
      if (ref === ownRef) {
        fragment.appendChild(document.createTextNode(ref));
      } else {
        const span = document.createElement("span");
        if (knownRefs.has(ref)) {
          span.className = "crossref";
          span.dataset.ref = ref;
        } else {
          span.className = "crossref-external";
        }
        span.textContent = ref;
        fragment.appendChild(span);
      }
      lastIndex = match.index + ref.length;
    }
    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.slice(lastIndex)));
    }
    parent.replaceChild(fragment, textNode);
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

/** Group siblings by type, sorted IR→AMC→GM→CS. */
function groupSiblingsByType(siblings: NodeSummary[]): Map<NodeType, NodeSummary[]> {
  const groups = new Map<NodeType, NodeSummary[]>();
  const sorted = [...siblings].sort((a, b) => typeOrder(a.node_type) - typeOrder(b.node_type));
  for (const s of sorted) {
    const list = groups.get(s.node_type) ?? [];
    list.push(s);
    groups.set(s.node_type, list);
  }
  return groups;
}

export function ArticlePanel({ node, loading, error, onNavigate, knownRefs, siblings, onSelectSibling }: Props) {
  const articleRef = useRef<HTMLElement>(null);
  const [expandedType, setExpandedType] = useState<NodeType | null>(null);

  // Reset expanded list when navigating to a different article
  useEffect(() => { setExpandedType(null); }, [node?.node_id]);

  useEffect(() => {
    const container = articleRef.current;
    if (!container || !node || !knownRefs) return;
    const ownRefMatch = node.reference_code.match(/21\.[A-Z]\.\d+[A-Z]?/);
    const ownRef = ownRefMatch ? ownRefMatch[0] : "";
    linkifyDom(container, ownRef, knownRefs);
  }, [node?.node_id, knownRefs]);

  if (loading) {
    return <main className="article-panel article-empty">Loading…</main>;
  }
  if (error) {
    return <main className="article-panel article-empty error">{error}</main>;
  }
  if (!node) {
    return (
      <main className="article-panel article-empty">
        Select an article in the tree to see its content.
      </main>
    );
  }

  function handleArticleClick(e: React.MouseEvent<HTMLElement>) {
    const target = e.target as HTMLElement;
    if (target.classList.contains("crossref")) {
      const ref = target.dataset.ref;
      if (ref && onNavigate) onNavigate(ref);
    }
  }

  const siblingGroups = siblings && siblings.length > 1 ? groupSiblingsByType(siblings) : null;

  return (
    <main className="article-panel">
      <header className="article-header">
        <div className={`article-header-title article-header-${node.node_type}`}>
          <span className={`badge badge-${node.node_type}`}>{node.node_type}</span>
          <span className="article-ref">{node.reference_code}</span>
          {node.title && <span className="article-title-text">{node.title}</span>}
        </div>

        {/* Variant tabs — only shown when this article has multiple type variants */}
        {siblingGroups && (
          <div className="article-variants-wrapper">
            <div className="article-variants">
              {Array.from(siblingGroups.entries()).map(([type, nodes]) => {
                const isActive = type === node.node_type;
                const isExpanded = expandedType === type;
                const multi = nodes.length > 1;

                function handleClick() {
                  if (multi) {
                    // Always just toggle the list — user picks from it
                    setExpandedType(isExpanded ? null : type);
                  } else {
                    // Single node: navigate directly
                    onSelectSibling && onSelectSibling(nodes[0]);
                    setExpandedType(null);
                  }
                }

                return (
                  <button
                    key={type}
                    className={`article-variant-tab variant-${type}${isActive ? " is-active" : ""}${isExpanded ? " is-expanded" : ""}`}
                    onClick={handleClick}
                    title={multi ? `${nodes.length} ${type} — cliquer pour lister` : undefined}
                  >
                    <span className={`badge badge-${type}`}>{type}</span>
                    {multi && (
                      <span className="variant-count">
                        ×{nodes.length}
                        <span className="variant-chevron">{isExpanded ? "▲" : "▼"}</span>
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Expanded list for multi-node types */}
            {expandedType && siblingGroups.get(expandedType) && (
              <ul className="article-variant-list">
                {siblingGroups.get(expandedType)!.map((n) => (
                  <li
                    key={n.node_id}
                    className={`article-variant-list-item${n.node_id === node.node_id ? " is-current" : ""}`}
                    onClick={() => {
                      onSelectSibling && onSelectSibling(n);
                      if (n.node_id === node.node_id) setExpandedType(null);
                    }}
                  >
                    <span className={`badge badge-${n.node_type}`}>{n.node_type}</span>
                    <span className="article-variant-list-ref">{n.reference_code}</span>
                    {n.title && <span className="article-variant-list-title">{n.title}</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        <div className="article-header-meta">
          <span className="article-hierarchy">{node.hierarchy_path}</span>
          <span className="article-header-meta-right">
            {node.applicability_date && (
              <span className="article-date" title="Applicable from">
                Applicable: {formatDate(node.applicability_date)}
              </span>
            )}
            {node.regulatory_source && (
              <span className="article-reg-source">{node.regulatory_source}</span>
            )}
          </span>
        </div>
      </header>

      {node.content_html ? (
        <article
          ref={articleRef}
          className="article-html"
          dangerouslySetInnerHTML={{ __html: node.content_html }}
          onClick={handleArticleClick}
        />
      ) : (
        <article>
          {node.content_text.split("\n").map((line, i) => (
            <p key={i}>{line}</p>
          ))}
        </article>
      )}
    </main>
  );
}
