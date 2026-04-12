import { useEffect, useRef, useState } from "react";
import type { CatalogEntry } from "../api";
import type { DocumentInfo } from "../types";

// Domain palette — same as NavigatePanel
const DOMAIN_META: Record<string, { bg: string; text: string; border: string; label: string }> = {
  "framework":                { bg: "#1e293b", text: "#f1f5f9",  border: "#334155", label: "Framework" },
  "initial-airworthiness":    { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Initial Airworthiness" },
  "avionics":                 { bg: "#78350f", text: "#fde68a",  border: "#d97706", label: "Initial Airworthiness" },
  "continuing-airworthiness": { bg: "#1e3a8a", text: "#dbeafe",  border: "#2563eb", label: "Continuing Airworthiness" },
  "air-operations":           { bg: "#4c1d95", text: "#e9d5ff",  border: "#7c3aed", label: "Air Operations" },
  "aircrew":                  { bg: "#0c4a6e", text: "#bae6fd",  border: "#0284c7", label: "Aircrew" },
  "aerodromes":               { bg: "#134e4a", text: "#99f6e4",  border: "#14b8a6", label: "Aerodromes" },
};

const DOMAIN_ORDER = [
  "framework", "initial-airworthiness", "continuing-airworthiness",
  "air-operations", "aircrew", "aerodromes",
];

function domainMeta(domain: string) {
  return DOMAIN_META[domain] ?? { bg: "#1e293b", text: "#f1f5f9", border: "#334155", label: domain };
}

// For the strip active tab: map source_root → catalog entry domain
function domainForSource(source: string, catalog: CatalogEntry[]): string {
  const entry = catalog.find((e) => e.source_root === source);
  return entry?.domain ?? "framework";
}

interface Props {
  documents: DocumentInfo[];
  selectedSource: string | null;
  onSelectSource: (source: string) => void;
  catalog: CatalogEntry[];
}

export function DocStrip({ documents, selectedSource, onSelectSource, catalog }: Props) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handle(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handle);
    return () => document.removeEventListener("mousedown", handle);
  }, [open]);

  // Active tab details
  const activeDoc = documents.find((d) => d.source === selectedSource);
  const activeDomain = selectedSource ? domainForSource(selectedSource, catalog) : "framework";
  const activeMeta = domainMeta(activeDomain);

  // Group catalog by domain for the dropdown
  const byDomain = new Map<string, CatalogEntry[]>();
  for (const entry of catalog) {
    const key = entry.domain === "avionics" ? "initial-airworthiness" : entry.domain;
    if (!byDomain.has(key)) byDomain.set(key, []);
    byDomain.get(key)!.push(entry);
  }

  // Map source_root → DocumentInfo for node counts
  const docByRoot = new Map(documents.map((d) => [d.source, d]));

  return (
    <div className="doc-strip" ref={dropdownRef}>
      {/* Active document tab */}
      {activeDoc && (
        <div
          className="doc-strip-tab is-active"
          style={{ background: activeMeta.bg, color: activeMeta.text, borderColor: activeMeta.border, borderBottomColor: activeMeta.bg }}
        >
          <span className="doc-strip-domain-dot" style={{ background: activeMeta.text }} />
          <span className="doc-strip-label">{activeDoc.label}</span>
          <span className="doc-strip-count" style={{ background: "rgba(255,255,255,0.2)", color: activeMeta.text }}>
            {activeDoc.nodeCount}
          </span>
        </div>
      )}

      {/* Separator */}
      {activeDoc && <div className="doc-strip-sep" />}

      {/* "All Documents" dropdown button */}
      <button
        className={"doc-strip-all-btn" + (open ? " is-open" : "")}
        onClick={() => setOpen(!open)}
      >
        <span>All Documents</span>
        <span className="doc-strip-all-chevron">{open ? "▲" : "▼"}</span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="doc-strip-dropdown">
          <div className="dsd-header">EASA Regulatory Framework</div>
          <div className="dsd-body">
            {DOMAIN_ORDER.filter((d) => byDomain.has(d)).map((domainKey) => {
              const meta = domainMeta(domainKey);
              const entries = byDomain.get(domainKey)!;
              return (
                <div key={domainKey} className="dsd-section">
                  <div
                    className="dsd-section-header"
                    style={{ background: meta.bg, color: meta.text }}
                  >
                    {meta.label}
                  </div>
                  {entries.map((entry) => {
                    const doc = entry.source_root ? docByRoot.get(entry.source_root) : null;
                    const isActive = entry.source_root === selectedSource;
                    return (
                      <button
                        key={entry.id}
                        className={"dsd-item" + (isActive ? " is-active" : "") + (!entry.indexed ? " is-unindexed" : "")}
                        style={isActive ? { borderLeftColor: meta.border } : {}}
                        onClick={() => {
                          if (entry.source_root && doc) {
                            onSelectSource(entry.source_root);
                            setOpen(false);
                          }
                        }}
                        disabled={!entry.indexed || !entry.source_root}
                        title={!entry.indexed ? "Not indexed — not available in Consult" : entry.name}
                      >
                        <span className="dsd-item-short" style={isActive ? { color: meta.border } : {}}>
                          {entry.short}
                        </span>
                        <span className="dsd-item-name">{entry.name.replace(/^[^—]+—\s*/, "")}</span>
                        <span className="dsd-item-right">
                          {entry.indexed && doc && (
                            <span className="dsd-item-count">{doc.nodeCount}</span>
                          )}
                          {!entry.indexed && (
                            <span className="dsd-item-na">—</span>
                          )}
                        </span>
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
