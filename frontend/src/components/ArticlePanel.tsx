import type { NodeDetail } from "../types";

interface Props {
  node: NodeDetail | null;
  loading: boolean;
  error: string | null;
}

export function ArticlePanel({ node, loading, error }: Props) {
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
  return (
    <main className="article-panel">
      <header>
        <span className={`badge badge-${node.node_type}`}>{node.node_type}</span>
        <h1>{node.reference_code}</h1>
        {node.title && <p className="article-subtitle">{node.title}</p>}
        <p className="article-hierarchy">{node.hierarchy_path}</p>
      </header>
      {node.content_html ? (
        <article
          className="article-html"
          dangerouslySetInnerHTML={{ __html: node.content_html }}
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
