import type { DocumentInfo, NodeSummary } from "./types";

export interface ArticleGroup {
  articleCode: string;   // e.g. "21.A.91"
  nodes: NodeSummary[];  // sorted: IR first, then AMC/GM
}

export interface SectionGroup {
  name: string;          // e.g. "Section 1 – Voice Channel Spacing (VCS)" or "" for flat subparts
  articles: ArticleGroup[];
}

export interface SubpartGroup {
  name: string;          // e.g. "SUBPART D — CHANGES TO TYPE-CERTIFICATES ..."
  sections: SectionGroup[];
  /** Flat list of all articles across all sections — convenience for search & counts. */
  articles: ArticleGroup[];
}

/**
 * Extract the bare article code for grouping CS + AMC + GM under the same
 * article in the tree. Strips the type prefix and sub-paragraph references.
 *
 *   "21.A.91"              → "21.A.91"
 *   "AMC 21.A.91"          → "21.A.91"
 *   "CS 25.143"            → "25.143"
 *   "AMC 25.143(a)"        → "25.143"
 *   "AMC1 25.143(b)(1)"    → "25.143"
 *   "ORO.GEN.105"          → "ORO.GEN.105"
 *   "AMC1 ORO.GEN.105"     → "ORO.GEN.105"
 *   "CS ACNS.B.GEN.1005"   → "ACNS.B.GEN.1005"
 *   "AMC ACNS.B.GEN.1005"  → "ACNS.B.GEN.1005"
 */
export function articleCode(node: NodeSummary): string {
  // Strip leading type prefix: "AMC1 ", "GM2 ", "CS ", "AMC ", "GM " …
  const bare = node.reference_code.replace(/^(?:AMC\d*|GM\d*|CS)\s+/, "");
  // Strip trailing sub-paragraph refs: "(a)", "(b)(1)", "(a);(b)" …
  return bare.replace(/\s*\(.*$/, "").trim();
}

/** Sort IR/CS first (base articles), then AMC, then GM. */
export function typeOrder(t: string): number {
  const order: Record<string, number> = { IR: 0, CS: 0, AMC: 1, GM: 2 };
  return order[t] ?? 9;
}

/** Sort article codes like 21.A.91 naturally, not lexicographically. */
function compareArticleCodes(a: string, b: string): number {
  const na = parseInt(a.split(".").pop()?.replace(/[A-Z]/g, "") ?? "0", 10);
  const nb = parseInt(b.split(".").pop()?.replace(/[A-Z]/g, "") ?? "0", 10);
  if (na !== nb) return na - nb;
  return a.localeCompare(b);
}

/**
 * Human-readable label from a hierarchy_path root segment.
 *   "Annex I"                                       → "Part 21"
 *   "Annex Ib"                                      → "Part 21 Light"
 *   "ANNEX IV (Part-CAT)"                           → "Part-CAT"
 *   "ANNEX IV (Part-ADR.OPS)"                       → "Part-ADR.OPS"
 *   "Easy Access Rules for Large Aeroplanes (CS-25)"→ "CS-25"
 *   "Easy Access Rules for ... (CS-ACNS)"           → "CS-ACNS"
 */
function docLabel(root: string): string {
  // "... (CS-XXX)" → "CS-XXX"
  const csMatch = root.match(/\((CS-[A-Z0-9]+)\)/i);
  if (csMatch) return csMatch[1].toUpperCase();
  // "ANNEX X (Part-YYY)" or "ANNEX X (Part-YYY.ZZZ)" → "Part-YYY" / "Part-YYY.ZZZ"
  const partMatch = root.match(/\(Part-([A-Z0-9.]+)\)/i);
  if (partMatch) return `Part-${partMatch[1].toUpperCase()}`;
  // Annex I / Annex Ib are Part 21's two sections
  if (/^annex ib$/i.test(root.trim())) return "Part 21 Light";
  if (/^annex i$/i.test(root.trim()))  return "Part 21";
  return root;
}

/**
 * Derive the list of distinct documents from a flat node list.
 * Groups by the root segment of hierarchy_path — that is the regulatory document identity.
 * regulatory_source is citation metadata (ED Decision ref), not a document-level grouping.
 */
export function buildDocuments(nodes: NodeSummary[]): DocumentInfo[] {
  const counts = new Map<string, number>();
  for (const node of nodes) {
    if (node.node_type === "GROUP") continue;
    const root = node.hierarchy_path.split(" / ")[0] ?? "Unknown";
    counts.set(root, (counts.get(root) ?? 0) + 1);
  }
  return Array.from(counts.entries())
    .map(([source, nodeCount]) => ({ source, label: docLabel(source), nodeCount }))
    .sort((a, b) => a.label.localeCompare(b.label));
}

function sortArticles(groups: ArticleGroup[]): ArticleGroup[] {
  return groups.sort((a, b) => compareArticleCodes(a.articleCode, b.articleCode));
}

function sortNodes(ns: NodeSummary[]): void {
  ns.sort((a, b) => {
    const to = typeOrder(a.node_type) - typeOrder(b.node_type);
    if (to !== 0) return to;
    const aApp = a.reference_code.startsWith("Appendix") ? 1 : 0;
    const bApp = b.reference_code.startsWith("Appendix") ? 1 : 0;
    if (aApp !== bApp) return aApp - bApp;
    return a.reference_code.localeCompare(b.reference_code);
  });
}

/**
 * Group a flat list of nodes into Subpart → Section → Article → [nodes].
 * Documents without sections (e.g. CS-25) produce a single unnamed section per subpart.
 * Expects nodes pre-filtered by document source and active types.
 */
/** Canonical label map: normalizedKey -> preferred display label */
function canonicalLabel(
  labelMap: Map<string, string>,
  raw: string
): string {
  const key = raw.toUpperCase().replace(/\s+/g, " ").trim();
  if (!labelMap.has(key)) {
    labelMap.set(key, raw);
  } else {
    // Prefer the ALL-CAPS version (PDF source, more authoritative)
    const existing = labelMap.get(key)!;
    if (raw === raw.toUpperCase() && existing !== raw) {
      labelMap.set(key, raw);
    }
  }
  return key;
}

export function buildTree(nodes: NodeSummary[]): SubpartGroup[] {
  // bySubpart > bySection > byArticle — keyed by normalized uppercase
  const bySubpart = new Map<string, Map<string, Map<string, NodeSummary[]>>>();
  const subpartLabels = new Map<string, string>();
  const sectionLabels = new Map<string, string>();

  for (const node of nodes) {
    if (node.node_type === "GROUP") continue;
    const parts = node.hierarchy_path.split(" / ");

    const structuralParts = parts.length > 1 ? parts.slice(1) : parts;
    const explicitSubpart = structuralParts.find((p) => /^\(?SUBPART/i.test(p));
    // If no explicit SUBPART, use the first structural segment (e.g. CS-ACNS "SECTION 1 – PBN")
    const subpartRaw = explicitSubpart ?? (structuralParts.length > 0 ? structuralParts[0] : "Other");
    // Find the section segment — only when subpart is explicit
    const sectionRaw = explicitSubpart
      ? (structuralParts.find((p) => /^SECTION\s+\d/i.test(p)) ?? "")
      : (structuralParts.length > 1 ? structuralParts[1] : "");

    const subpartKey = canonicalLabel(subpartLabels, subpartRaw);
    const sectionKey = canonicalLabel(sectionLabels, sectionRaw);
    const art = articleCode(node);

    if (!bySubpart.has(subpartKey)) bySubpart.set(subpartKey, new Map());
    const bySec = bySubpart.get(subpartKey)!;
    if (!bySec.has(sectionKey)) bySec.set(sectionKey, new Map());
    const byArt = bySec.get(sectionKey)!;
    if (!byArt.has(art)) byArt.set(art, []);
    byArt.get(art)!.push(node);
  }

  const result: SubpartGroup[] = [];

  for (const [subpartKey, bySec] of bySubpart) {
    const subpartName = subpartLabels.get(subpartKey) ?? subpartKey;
    const sections: SectionGroup[] = [];

    for (const [sectionKey, byArt] of bySec) {
      const sectionName = sectionLabels.get(sectionKey) ?? sectionKey;
      const articleGroups: ArticleGroup[] = [];
      for (const [code, ns] of byArt) {
        sortNodes(ns);
        articleGroups.push({ articleCode: code, nodes: ns });
      }
      sections.push({ name: sectionName, articles: sortArticles(articleGroups) });
    }

    // Sort sections: unnamed first, then by name
    sections.sort((a, b) => {
      if (!a.name && !b.name) return 0;
      if (!a.name) return -1;
      if (!b.name) return 1;
      return a.name.localeCompare(b.name);
    });

    // Flat article list across all sections (for search results & leaf counts)
    const allArticles = sections.flatMap((s) => s.articles);

    result.push({ name: subpartName, sections, articles: allArticles });
  }

  result.sort((a, b) => a.name.localeCompare(b.name));
  return result;
}
