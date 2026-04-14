import React, { useEffect, useRef, useState } from "react";
import type { CatalogEntry, VersionCheckResult } from "../api";
import type { NodeDetail, NodeSummary, NodeType } from "../types";
import { typeOrder } from "../tree";

/**
 * Post-process EASA HTML: detect paragraph label level in flat <ol> items
 * and inject easa-li-l1 / easa-li-l2 / easa-li-l3 / easa-li-l4 classes.
 *
 * EASA hierarchy (from PDF x-coordinates):
 *   L1  (a) (b) (c) …          x=72   padding 0
 *   L2  (1) (2) (3) …          x=100  padding 2.33rem
 *   L3  (i) (ii) (iii) …       x=129  padding 4.75rem
 *   L4  (A) (B) (C) …          x=157  padding 7.08rem
 */
function labelLevel(label: string, dotStyle = false): string {
  const l = label.toLowerCase();
  // Dot-style section numbers  1.  2.  13.  → L0 (flush, section heading)
  if (dotStyle && /^\d+$/.test(label)) return "easa-li-l0";
  // Dot-style letters  a.  b.  → L1
  if (dotStyle && /^[a-z]$/.test(l)) return "easa-li-l1";
  // Uppercase single letter → L4
  if (/^[A-Z]$/.test(label)) return "easa-li-l4";
  // Roman numerals → L3
  if (/^(i{1,3}|iv|vi{0,3}|ix|xi{0,3})$/.test(l) && isNaN(Number(label))) return "easa-li-l3";
  // Lowercase single letter → L1
  if (/^[a-z]$/.test(l)) return "easa-li-l1";
  // Number → L2
  return "easa-li-l2";
}

/**
 * Group consecutive <p> elements that start with an em-dash (— ) into a <ul>.
 * These are bullet lists in the original PDF rendered as flat paragraphs.
 */
function groupDashLists(html: string): string {
  // Match a <p...> that starts with — (em-dash, optionally nbsp before text)
  const DASH_P = /(<p(?:[^>]*)>)\s*\u2014\s*([\s\S]*?)(<\/p>)/g;
  // Replace all dash-paragraphs with a sentinel li, then wrap consecutive ones in <ul>
  const withLi = html.replace(DASH_P, (_m, _open, content, _close) =>
    `<li class="easa-dash-item">${content.trim()}</li>`
  );
  // Wrap consecutive <li class="easa-dash-item"> runs in <ul class="easa-dash-list">
  return withLi.replace(
    /(<li class="easa-dash-item">[\s\S]*?<\/li>)(\s*<li class="easa-dash-item">[\s\S]*?<\/li>)*/g,
    (match) => `<ul class="easa-dash-list">${match}</ul>`
  );
}

function injectEasaIndent(html: string): string {
  // Step 1a: parenthesised labels  (a)  (1)  (i)  (A)
  let lastLevel = "easa-li-l1";
  let processed = html.replace(
    /<li([^>]*)>(\s*)\(([a-zA-Z]+|[0-9]+)\)/g,
    (_match, attrs, _ws, label) => {
      const level = labelLevel(label);
      lastLevel = level;
      return `<li${attrs} class="${level}">(${label})`;
    }
  );

  // Step 1b: dot-suffixed labels  a.  b.  1.  10.  — plain, in <em>, or in <strong>
  // Pattern: <li...>(<em>|<strong>)?LABEL.(</em>|</strong>|&emsp;)
  processed = processed.replace(
    /<li([^>]*)>(\s*)(?:<(?:em|strong)>)?([a-zA-Z]|\d{1,2})\.<\/(?:em|strong)>|<li([^>]*)>(\s*)([a-zA-Z]|\d{1,2})\.(?=&emsp;)/g,
    (match, a1, _w1, l1, a2, _w2, l2) => {
      const attrs = a1 ?? a2 ?? "";
      const label = l1 ?? l2 ?? "";
      const level = labelLevel(label, true);
      lastLevel = level;
      // Reconstruct preserving original format (em tag already in original if a1 matched)
      return match.replace(/<li([^>]*)>/, `<li${attrs} class="${level}">`);
    }
  );

  // Step 2: indent <p> elements that sit between </ol> and <ol> (continuation paragraphs)
  // They are body text of the last <li>, so they go one level deeper.
  const LEVELS = ["easa-li-l0", "easa-li-l1", "easa-li-l2", "easa-li-l3", "easa-li-l4"];
  const continuationLevel = LEVELS[Math.min(LEVELS.indexOf(lastLevel) + 1, LEVELS.length - 1)];
  processed = processed.replace(
    /<\/ol>\n(<p(?:[^>]*)>[^<]*<\/p>\n)<ol>/g,
    (_match, para) => {
      const indented = para.replace(/<p((?:[^>]*))>/, `<p$1 class="easa-continuation ${continuationLevel}">`);
      return `</ol>\n${indented}<ol>`;
    }
  );

  return processed;
}

interface Props {
  node: NodeDetail | null;
  loading: boolean;
  error: string | null;
  onNavigate?: (refCode: string) => void;
  knownRefs?: Set<string>;
  /** All IR/AMC/GM nodes sharing the same article code (includes current node). */
  siblings?: NodeSummary[] | null;
  onSelectSibling?: (node: NodeSummary) => void;
  /** Catalog metadata for the currently selected document */
  catalogEntry?: CatalogEntry | null;
  /** Version staleness check result for the current document */
  versionCheck?: VersionCheckResult | null;
}

// Matches EASA article references:
//   prefixed  : AMC 25.1309, GM1 21.A.91, CS 25.143
//   alpha-led : 21.A.20, M.A.302, ACNS.B.GEN.1005
//   num-led   : 25.143, 25.1309
const ANY_REF_RE = /\b(?:(?:AMC\d*|GM\d*|CS|IR)\s+(?:\d{2,}\.[\w.]+|(?:[A-Z]+\.){1,3}[A-Z0-9]+(?:\.[A-Z0-9]+)*)|(?:[A-Z]+\.){1,3}[A-Z0-9]+(?:\.[A-Z0-9]+)*|\d{2,}\.[A-Z0-9]+(?:\.[A-Z0-9]+)*)\b/g;

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
  // Build bare-code → full ref lookup (e.g. "25.1309" → "CS 25.1309")
  // Priority: IR > CS > AMC > GM (prefer base article over commentary)
  const TYPE_PRIORITY: Record<string, number> = { IR: 0, CS: 1, AMC: 2, GM: 3 };
  const bareToFull = new Map<string, string>();
  const barePriority = new Map<string, number>();
  for (const full of knownRefs) {
    const bare = full.replace(/^(?:AMC\d*|GM\d*|CS|IR)\s+/, "").replace(/\([^)]*\).*$/, "").trim();
    const prefix = full.split(" ")[0].replace(/\d+$/, "");
    const prio = TYPE_PRIORITY[prefix] ?? 9;
    if (!bareToFull.has(bare) || prio < (barePriority.get(bare) ?? 9)) {
      bareToFull.set(bare, full);
      barePriority.set(bare, prio);
    }
    // Also register prefixed base form: "AMC 25.1301(a)(2)" → key "AMC 25.1301"
    const prefixedBase = full.replace(/\([^)]*\).*$/, "").trim();
    if (prefixedBase !== full && !bareToFull.has(prefixedBase)) {
      bareToFull.set(prefixedBase, full);
    }
  }

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
      // Check exact match or bare-code match
      const fullRef = knownRefs.has(ref) ? ref : (bareToFull.get(ref) ?? null);
      if (ref === ownRef || ref === ownRef.replace(/^(?:AMC\d*|GM\d*|CS|IR)\s+/, "")) {
        fragment.appendChild(document.createTextNode(ref));
      } else {
        const span = document.createElement("span");
        if (fullRef) {
          span.className = "crossref";
          span.dataset.ref = fullRef;
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

const DOMAIN_META: Record<string, { bg: string; text: string; label: string }> = {
  "framework":                { bg: "#1e293b", text: "#f1f5f9",  label: "Framework" },
  "initial-airworthiness":    { bg: "#78350f", text: "#fde68a",  label: "Initial Airworthiness" },
  "avionics":                 { bg: "#78350f", text: "#fde68a",  label: "Initial Airworthiness" },
  "continuing-airworthiness": { bg: "#1e3a8a", text: "#dbeafe",  label: "Continuing Airworthiness" },
  "air-operations":           { bg: "#4c1d95", text: "#e9d5ff",  label: "Air Operations" },
  "aircrew":                  { bg: "#0c4a6e", text: "#bae6fd",  label: "Aircrew" },
  "aerodromes":               { bg: "#134e4a", text: "#99f6e4",  label: "Aerodromes" },
};

function DocInfoPage({ entry, versionCheck }: { entry: CatalogEntry | null; versionCheck?: VersionCheckResult | null }) {
  if (!entry) {
    return (
      <main className="article-panel article-empty">
        Select an article in the tree.
      </main>
    );
  }
  const meta = DOMAIN_META[entry.domain] ?? DOMAIN_META["framework"];
  return (
    <main className="article-panel doc-info-page">
      <header className="doc-info-header" style={{ background: meta.bg, color: meta.text }}>
        <div className="doc-info-domain">{meta.label}</div>
        <div className="doc-info-short">{entry.short}</div>
        <div className="doc-info-name">{entry.name}</div>
      </header>
      <div className="doc-info-body">
        <p className="doc-info-desc">{entry.description}</p>
        <div className="doc-info-chips">
          {entry.version_label && (
            <span className="doc-info-chip doc-info-chip--version">
              {entry.version_label}
            </span>
          )}
          {entry.pub_date && (
            <span className="doc-info-chip doc-info-chip--date">
              {formatDate(entry.pub_date)}
            </span>
          )}
          {entry.node_count > 0 && (
            <span className="doc-info-chip doc-info-chip--count">
              {entry.node_count} nodes
            </span>
          )}
        </div>
        {versionCheck?.is_outdated && versionCheck.latest_version && (
          <div className="doc-info-amended">
            <span>⚠</span>
            <span>
              Indexed version outdated — <strong>{versionCheck.latest_version}</strong> is available on EASA.
              The content may not reflect the latest regulatory requirements.
            </span>
          </div>
        )}
        <a
          href={entry.easa_url}
          target="_blank"
          rel="noopener noreferrer"
          className="doc-info-link"
        >
          Open on EASA website ↗
        </a>
      </div>
    </main>
  );
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

/**
 * Returns true when a line starts a new logical paragraph in PDF plain-text:
 *   "1 General"  "1.1 Something"  "a. text"  "(a) text"  "Note:"  "—"  blank
 */
function isParaStart(line: string): boolean {
  if (!line) return true;
  // Numbered section: "1 General" or "1.1 Analysis..." or "1.4.2 For..."
  if (/^\d+(\.\d+)*\s+\S/.test(line)) return true;
  // Letter list: "a. text"  "b. text"
  if (/^[a-z]\.\s/.test(line)) return true;
  // Paren list: "(a) text"  "(1) text"  "(i) text"
  if (/^\([a-z0-9]{1,4}\)\s/.test(line)) return true;
  // Half-paren list: "a)"  "b)"  alone on a line or followed by text
  if (/^[a-z]\)/.test(line)) return true;
  // Note / Note N:
  if (/^Note\b/i.test(line)) return true;
  // Em-dash or bullet
  if (/^[—–\-•]\s/.test(line)) return true;
  return false;
}

/**
 * Classify indent level from a paragraph's first token.
 */
function paraClass(first: string): string {
  if (/^[a-z]\.\s/.test(first)) return "pt-para pt-indent-1";
  if (/^[a-z]\)/.test(first)) return "pt-para pt-indent-1";
  if (/^\([a-z]{1,3}\)\s/.test(first)) {
    const m = first.match(/^\(([a-z]{1,3})\)/);
    const marker = m ? m[1] : "";
    if (/^(i{1,4}|iv|vi{0,3}|ix|x{1,3})$/i.test(marker)) return "pt-para pt-indent-3";
    return "pt-para pt-indent-1";
  }
  if (/^\(\d+\)\s/.test(first)) return "pt-para pt-indent-2";
  if (/^Note\b/i.test(first)) return "pt-para pt-note";
  return "pt-para";
}

/**
 * Render plain-text content (PDF-parsed) with smart paragraph grouping:
 * - Wrapped lines belonging to the same sentence are joined with a space
 * - A new paragraph is started when the next line signals a new section/list item
 * - Numbered section headings (e.g. "1 General", "2 Flight demonstrations") → <h4>
 * - Page footer lines (Powered by EASA…) are stripped
 */
function renderPlainText(text: string, _knownRefs: Set<string>, _ownRef: string): React.ReactNode[] {
  // Strip page footer lines before paragraph analysis
  const rawLines = text.split("\n").map(l => l.trim())
    .filter(l => !/^Powered by EASA\b/i.test(l));
  const elements: React.ReactNode[] = [];
  let buffer: string[] = [];

  const flush = () => {
    if (buffer.length === 0) return;
    const joined = buffer.join(" ").trim();
    buffer = [];
    if (!joined) return;

    // Pure section heading: "1 General" or "2 Flight demonstrations" (short title, no sub-number)
    const headingMatch = joined.match(/^(\d+)\s+([A-Z][^.]{2,60})$/);
    if (headingMatch) {
      elements.push(
        <h4 key={elements.length} className="pt-section-heading">
          <span className="pt-section-num">{headingMatch[1]}</span>
          {headingMatch[2]}
        </h4>
      );
      return;
    }

    const cls = paraClass(joined);
    elements.push(<p key={elements.length} className={cls}>{joined}</p>);
  };

  // Collect consecutive table rows (lines with \t) into a single <table>
  let tableRows: string[][] = [];

  const flushTable = () => {
    if (tableRows.length === 0) return;
    const rows = tableRows;
    tableRows = [];
    elements.push(
      <table key={elements.length} className="pt-table">
        <tbody>
          {rows.map((cols, ri) => (
            <tr key={ri}>
              {cols.map((c, ci) => <td key={ci}>{c}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    );
  };

  for (let i = 0; i < rawLines.length; i++) {
    const line = rawLines[i];

    if (!line) {
      flush();
      flushTable();
      continue;
    }

    // Tab-separated line → table row
    if (line.includes("\t")) {
      flush(); // flush any pending paragraph first
      tableRows.push(line.split("\t"));
      continue;
    }

    // Non-tab line after table rows → flush table
    if (tableRows.length > 0 && !line.includes("\t")) {
      flushTable();
    }

    // If this line starts a new paragraph, flush the previous one first
    if (buffer.length > 0 && isParaStart(line)) {
      flush();
    }

    buffer.push(line);
  }
  flush();
  flushTable();
  return elements;
}


export function ArticlePanel({ node, loading, error, onNavigate, knownRefs, siblings, onSelectSibling, catalogEntry, versionCheck }: Props) {
  const articleRef = useRef<HTMLElement>(null);
  const [expandedType, setExpandedType] = useState<NodeType | null>(null);

  // Reset expanded list when navigating to a different article
  useEffect(() => { setExpandedType(null); }, [node?.node_id]);

  useEffect(() => {
    const container = articleRef.current;
    if (!container || !node || !knownRefs) return;

    // Strip leading metadata lines duplicated in the header (ED Decision, AMC No., See AMC...)
    const HEADER_RE = /^\s*(?:ED\s+Decision\b|Commission\s+Regulation\b|\(See\s+(?:AMC|GM|CS)\b|\(See\s+also\b)/i;
    const walk = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const toRemove: Node[] = [];
    let n: Node | null;
    while ((n = walk.nextNode())) {
      const text = (n.textContent ?? "").trim();
      if (!text) continue;
      if (HEADER_RE.test(text)) {
        // Remove the parent element if it's a simple block (p, div, span)
        const p = n.parentElement;
        if (p && ["P", "DIV", "SPAN", "B", "STRONG"].includes(p.tagName) && (p.textContent ?? "").trim() === text) {
          toRemove.push(p);
        } else {
          toRemove.push(n);
        }
      } else {
        break; // stop at first non-metadata line
      }
    }
    toRemove.forEach(el => el.parentNode?.removeChild(el));

    // Add indentation based on EASA list markers
    // Level 1: (a)-(z)         → 1.5rem
    // Level 2: (1)-(99)        → 3rem
    // Level 3: (i),(ii),...    → 4.5rem
    const INDENT_RE = /^\s*\(([a-z]{1,3}|\d+)\)\s/;
    const ROMAN = /^(i{1,3}|iv|vi{0,3}|ix|x{1,3}|xi{1,3})$/i;
    for (const p of Array.from(container.querySelectorAll("p"))) {
      const text = p.textContent ?? "";
      const m = text.match(INDENT_RE);
      if (!m) continue;
      const marker = m[1];
      if (ROMAN.test(marker)) {
        p.classList.add("easa-indent-3");
      } else if (/^\d+$/.test(marker)) {
        p.classList.add("easa-indent-2");
      } else {
        p.classList.add("easa-indent-1");
      }
    }

    const ownRefMatch = node.reference_code.match(/\b(?:[A-Z]+\.){1,3}[A-Z0-9]+(?:\.[A-Z0-9]+)*\b/);
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
    return <DocInfoPage entry={catalogEntry ?? null} versionCheck={versionCheck} />;
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
      <div className="article-panel-top">
      <header className="article-header">
        <div className={`article-header-title article-header-${node.node_type}`}>
            <span className={`badge badge-${node.node_type}`}>{node.node_type}</span>
            <span className="article-ref">{node.reference_code}</span>
            {node.title && <span className="article-title-text">{node.title}</span>}
        </div>

        {/* Expanded list for multi-node types */}
        {expandedType && siblingGroups && siblingGroups.get(expandedType) && (
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
            {versionCheck?.is_outdated && versionCheck.latest_version && (
              <span
                className="article-outdated-badge"
                title={`Newer version available: ${versionCheck.latest_version}`}
              >
                ⚠ {versionCheck.latest_version}
              </span>
            )}
          </span>
        </div>
      </header>

      {node.content_html ? (
        <article
          ref={articleRef}
          className="article-html"
          dangerouslySetInnerHTML={{ __html: injectEasaIndent(groupDashLists(node.content_html)) }}
          onClick={handleArticleClick}
        />
      ) : (
        <article ref={articleRef} className="article-text" onClick={handleArticleClick}>
          {renderPlainText(node.content_text, knownRefs ?? new Set(), node.reference_code)}
        </article>
      )}
      </div>

    </main>
  );
}
