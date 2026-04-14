import { useState } from "react";
import type { CatalogEntry, VersionCheckResult } from "../api";

const CATEGORY_LABELS: Record<string, string> = {
  basic:  "Basic Regulation",
  ir:     "Implementing Rules",
  cs:     "Certification Specifications",
  amcgm:  "AMC & GM",
  other:  "Other",
};

const CATEGORY_ORDER = ["basic", "ir", "cs", "amcgm", "other"];

const CATEGORY_COLORS: Record<string, { accent: string; light: string; border: string }> = {
  basic:  { accent: "#0f172a", light: "#e2e8f0", border: "#94a3b8" },
  ir:     { accent: "#1e40af", light: "#dbeafe", border: "#3b82f6" },
  cs:     { accent: "#155e75", light: "#cffafe", border: "#06b6d4" },
  amcgm:  { accent: "#14532d", light: "#dcfce7", border: "#22c55e" },
  other:  { accent: "#44403c", light: "#e7e5e4", border: "#78716c" },
};
const DEFAULT_CAT_COLOR = { accent: "#44403c", light: "#e7e5e4", border: "#78716c" };

// Fine-grained domain palette — saturated, clearly distinct
// "initial-airworthiness" and "avionics" share the same visual group (teal)
const DOMAIN_COLORS: Record<string, { bg: string; text: string; border: string; label: string }> = {
  "framework":               { bg: "#1e293b", text: "#f1f5f9",  border: "#334155", label: "Framework" },
  "initial-airworthiness":   { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Initial Airworthiness" },
  "avionics":                { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Avionics / CNS" },
  "continuing-airworthiness":{ bg: "#1e3a8a", text: "#dbeafe",  border: "#2563eb", label: "Continuing Airworthiness" },
  "air-operations":          { bg: "#4c1d95", text: "#e9d5ff",  border: "#7c3aed", label: "Air Operations" },
  "aircrew":                 { bg: "#0c4a6e", text: "#bae6fd",  border: "#0284c7", label: "Aircrew" },
  "aerodromes":              { bg: "#134e4a", text: "#99f6e4",  border: "#14b8a6", label: "Aerodromes" },
  "other":                   { bg: "#292524", text: "#e7e5e4",  border: "#78716c", label: "Other" },
};

// Canonical filter pills
const DOMAIN_FILTER_ORDER = [
  "framework",
  "initial-airworthiness",
  "continuing-airworthiness",
  "air-operations",
  "aircrew",
  "aerodromes",
  "avionics",
  "other",
];

function domainFilterKey(domain: string): string {
  return domain;
}

interface Props {
  catalog: CatalogEntry[];
  versionChecks?: VersionCheckResult[];
  /** sources available in Explorer (from allNodes hierarchy roots) */
  availableSources: Set<string>;
  onNavigateTo: (source: string) => void;
}

function formatDate(d: string | null): string {
  if (!d) return "";
  const dt = new Date(d);
  return dt.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

function DocCard({
  entry,
  availableSources,
  onNavigateTo,
  isOutdated,
  latestVersion,
}: {
  entry: CatalogEntry;
  availableSources: Set<string>;
  onNavigateTo: (source: string) => void;
  isOutdated?: boolean;
  latestVersion?: string | null;
}) {
  // source_root is the exact first hierarchy_path root from DB — pass directly to App.
  // canExplore requires source_root to be present in availableSources (doc loaded in memory).
  const root = entry.source_root ?? null;
  const canExplore = entry.indexed && root !== null && availableSources.has(root);
  const inactive = entry.is_active === false;

  function handleClick() {
    if (canExplore && root) {
      onNavigateTo(root);
    } else if (!entry.indexed) {
      window.open(entry.easa_url, "_blank", "noopener");
    }
  }

  const domain = DOMAIN_COLORS[entry.domain] ?? DOMAIN_COLORS["initial-airworthiness"];

  if (entry.indexed) {
    return (
      <div
        className="nav-card nav-card--indexed"
        onClick={inactive ? undefined : handleClick}
        style={{ background: domain.bg, borderColor: domain.border, opacity: inactive ? 0.45 : 1, cursor: inactive ? "default" : undefined }}
        title={inactive ? `${entry.short} — not active in Astra` : canExplore ? `Open ${entry.short} in Consult` : `Indexed`}
      >
        <div className="nav-card-header">
          <span className="nav-card-short" style={{ color: domain.text }}>{entry.short}</span>
          <span className="nav-badge nav-badge--indexed" style={{ background: domain.border, color: domain.bg }}>
            ✓ Indexed
          </span>
        </div>
        <div className="nav-card-name" style={{ color: domain.text }}>{entry.name}</div>
        <div className="nav-card-desc" style={{ color: domain.text, opacity: 0.75 }}>{entry.description}</div>
        <div className="nav-card-meta">
          {entry.version_label ? (
            <span className="nav-meta-chip" style={{ background: domain.border, color: domain.bg }}>
              {entry.version_label}
            </span>
          ) : (
            <span className="nav-meta-chip" style={{ background: "rgba(255,255,255,0.08)", color: domain.text, opacity: 0.55, fontStyle: "italic" }}>
              version not recorded
            </span>
          )}
          {entry.pub_date ? (
            <span className="nav-meta-chip" style={{ background: "rgba(255,255,255,0.15)", color: domain.text }}>
              in force {formatDate(entry.pub_date)}
            </span>
          ) : null}
          {entry.node_count > 0 && (
            <span className="nav-meta-chip" style={{ background: "rgba(255,255,255,0.1)", color: domain.text, opacity: 0.8 }}>
              {entry.node_count} nodes
            </span>
          )}
        </div>
        {isOutdated && latestVersion && (
          <div className="nav-card-amended">
            <span className="nav-amended-badge">⚠ Newer version available: {latestVersion}</span>
          </div>
        )}
        {canExplore && (
          <div className="nav-card-action">
            <span className="nav-action-link" style={{ color: domain.text }}>Open in Consult →</span>
          </div>
        )}
      </div>
    );
  }

  return (
    <div
      className="nav-card nav-card--missing"
      onClick={inactive ? undefined : handleClick}
      style={{ opacity: inactive ? 0.4 : 1, cursor: inactive ? "default" : undefined }}
      title={inactive ? `${entry.short} — not active in Astra` : `Not indexed — open on easa.europa.eu`}
    >
      <div className="nav-card-header">
        <span className="nav-card-short">{entry.short}</span>
        <span className="nav-badge nav-badge--missing">Not available</span>
      </div>
      <div className="nav-card-name">{entry.name}</div>
      <div className="nav-card-desc">{entry.description}</div>
      <div className="nav-card-action">
        <span className="nav-action-link nav-action-link--ext">easa.europa.eu ↗</span>
      </div>
    </div>
  );
}

export function NavigatePanel({ catalog, versionChecks = [], availableSources, onNavigateTo }: Props) {
  const versionCheckMap = new Map(versionChecks.map((v) => [v.source_root, v]));
  const [search, setSearch] = useState("");
  // excludedCategories / excludedDomains / hiddenIndexState: empty = all visible (default)
  const [excludedCategories, setExcludedCategories] = useState<Set<string>>(new Set());
  const [excludedDomains, setExcludedDomains] = useState<Set<string>>(new Set());
  // "indexed" | "not-indexed" — if in set, hide those entries
  const [excludedIndexState, setExcludedIndexState] = useState<Set<string>>(new Set());

  function toggleIndexState(key: string) {
    setExcludedIndexState((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleCategory(key: string) {
    setExcludedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function toggleDomain(key: string) {
    setExcludedDomains((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  const q = search.toLowerCase().trim();

  const filtered = catalog.filter((e) => {
    if (excludedCategories.size > 0 && excludedCategories.has(e.category)) return false;
    if (excludedDomains.size > 0 && excludedDomains.has(domainFilterKey(e.domain))) return false;
    const stateKey = e.indexed ? "indexed" : "not-indexed";
    if (excludedIndexState.size > 0 && excludedIndexState.has(stateKey)) return false;
    if (q && !e.name.toLowerCase().includes(q) && !e.short.toLowerCase().includes(q)) return false;
    return true;
  });

  // Build category order dynamically: known order first, then any unknown categories
  const allCats = [...new Set(catalog.map((e) => e.category))];
  const orderedCats = [
    ...CATEGORY_ORDER.filter((c) => allCats.includes(c)),
    ...allCats.filter((c) => !CATEGORY_ORDER.includes(c)),
  ];
  const byCategory = orderedCats.reduce<Record<string, CatalogEntry[]>>((acc, cat) => {
    const items = filtered.filter((e) => e.category === cat);
    if (items.length > 0) acc[cat] = items;
    return acc;
  }, {});

  // Only show filter pills for domains that exist in the catalog
  const usedFilterKeys = new Set(catalog.map((e) => domainFilterKey(e.domain)));
  const allDomains = [...new Set(catalog.map((e) => e.domain))];
  const domainFilters = [
    ...DOMAIN_FILTER_ORDER.filter((d) => usedFilterKeys.has(d)),
    ...allDomains.filter((d) => !DOMAIN_FILTER_ORDER.includes(d) && usedFilterKeys.has(d)),
  ];
  const indexedCount = catalog.filter((e) => e.indexed).length;

  return (
    <div className="nav-panel">
      {/* ── Header ── */}
      <div className="nav-header">
        <div className="nav-header-top">
          <div>
            <h2 className="nav-title">EASA Regulatory Framework</h2>
            <p className="nav-subtitle">
              {indexedCount} of {catalog.length} documents indexed in Astra
            </p>
          </div>
          <input
            className="nav-search"
            placeholder="Search documents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {/* ── Filters ── */}
        <div className="nav-filters">
          <div className="nav-filter-group">
            <span className="nav-filter-label">Category</span>
            {CATEGORY_ORDER.filter((cat) => allCats.includes(cat)).map((cat) => {
              const cc = CATEGORY_COLORS[cat] ?? DEFAULT_CAT_COLOR;
              const isVisible = !excludedCategories.has(cat);
              return (
                <button
                  key={cat}
                  className="nav-filter-pill"
                  style={
                    isVisible
                      ? { background: cc.light, borderColor: cc.border, color: cc.accent }
                      : { background: "transparent", borderColor: cc.border, color: cc.border, opacity: 0.4 }
                  }
                  onClick={() => toggleCategory(cat)}
                  title={isVisible ? `Hide ${CATEGORY_LABELS[cat]}` : `Show ${CATEGORY_LABELS[cat]}`}
                >
                  {CATEGORY_LABELS[cat]}
                </button>
              );
            })}
          </div>
          <div className="nav-filter-group">
            <span className="nav-filter-label">Status</span>
            {(["indexed", "not-indexed"] as const).map((key) => {
              const isVisible = !excludedIndexState.has(key);
              const isIdx = key === "indexed";
              return (
                <button
                  key={key}
                  className="nav-filter-pill"
                  style={
                    isVisible
                      ? isIdx
                        ? { background: "#166534", borderColor: "#16a34a", color: "#bbf7d0" }
                        : { background: "#374151", borderColor: "#6b7280", color: "#d1d5db" }
                      : isIdx
                        ? { background: "transparent", borderColor: "#16a34a", color: "#16a34a", opacity: 0.4 }
                        : { background: "transparent", borderColor: "#6b7280", color: "#6b7280", opacity: 0.4 }
                  }
                  onClick={() => toggleIndexState(key)}
                  title={isVisible ? `Hide ${key}` : `Show ${key}`}
                >
                  {isIdx ? "✓ Indexed" : "Not indexed"}
                </button>
              );
            })}
          </div>
          <div className="nav-filter-group">
            <span className="nav-filter-label">Domain</span>
            {domainFilters.map((d) => {
              const dc = DOMAIN_COLORS[d] ?? { bg: "#292524", text: "#e7e5e4", border: "#78716c", label: d };
              const isVisible = !excludedDomains.has(d);
              return (
                <button
                  key={d}
                  className="nav-filter-pill"
                  style={
                    isVisible
                      ? { background: dc.bg, borderColor: dc.border, color: dc.text }
                      : { background: "transparent", borderColor: dc.border, color: dc.border, opacity: 0.45 }
                  }
                  onClick={() => toggleDomain(d)}
                  title={isVisible ? `Hide ${dc.label}` : `Show ${dc.label}`}
                >
                  {dc.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* ── Grid ── */}
      <div className="nav-body">
        {Object.entries(byCategory).map(([cat, entries]) => (
          <section key={cat} className="nav-section">
            <h3
              className="nav-section-title"
              style={{ color: CATEGORY_COLORS[cat]?.accent }}
            >
              <span
                className="nav-section-pill"
                style={{ background: CATEGORY_COLORS[cat]?.light, color: CATEGORY_COLORS[cat]?.accent }}
              >
                {CATEGORY_LABELS[cat]}
              </span>
              <span className="nav-section-count">
                {entries.filter((e) => e.indexed).length}/{entries.length} indexed
              </span>
            </h3>
            <div className="nav-grid">
              {entries.map((entry) => {
                const vc = entry.source_root ? versionCheckMap.get(entry.source_root) : undefined;
                return (
                  <DocCard
                    key={entry.id}
                    entry={entry}
                    availableSources={availableSources}
                    onNavigateTo={onNavigateTo}
                    isOutdated={vc?.is_outdated}
                    latestVersion={vc?.latest_version}
                  />
                );
              })}
            </div>
          </section>
        ))}

        {Object.keys(byCategory).length === 0 && (
          <div className="nav-empty">No documents match your search.</div>
        )}
      </div>
    </div>
  );
}
