import { useEffect, useRef } from "react";
import type { NodeDetail } from "../types";

interface Props {
  node: NodeDetail | null;
  loading: boolean;
  error: string | null;
  onNavigate?: (refCode: string) => void;
  knownRefs?: Set<string>;
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
  // Collect text nodes that contain at least one reference.
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
    // Don't re-process already-wrapped spans.
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

export function ArticlePanel({ node, loading, error, onNavigate, knownRefs }: Props) {
  const articleRef = useRef<HTMLElement>(null);

  // Run DOM-based linkification after the HTML is injected.
  useEffect(() => {
    const container = articleRef.current;
    if (!container || !node || !knownRefs) return;

    const ownRefMatch = node.reference_code.match(/21\.[A-Z]\.\d+[A-Z]?/);
    const ownRef = ownRefMatch ? ownRefMatch[0] : "";

    linkifyDom(container, ownRef, knownRefs);
  }, [node?.node_id, knownRefs]); // re-run only when the displayed node changes

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

  return (
    <main className="article-panel">
      <header className="article-header">
        <div className={`article-header-title article-header-${node.node_type}`}>
          <span className={`badge badge-${node.node_type}`}>{node.node_type}</span>
          <span className="article-ref">{node.reference_code}</span>
          {node.title && <span className="article-title-text">{node.title}</span>}
        </div>
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
