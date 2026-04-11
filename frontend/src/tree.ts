import type { NodeSummary } from "./types";

export interface ArticleGroup {
  articleCode: string;              // e.g. "21.A.91"
  nodes: NodeSummary[];             // IR first, then AMC/GM sorted
}

export interface SubpartGroup {
  name: string;                     // e.g. "SUBPART D — CHANGES TO TYPE-CERTIFICATES ..."
  articles: ArticleGroup[];
}

const ARTICLE_RE = /21\.A\.\d+[A-Z]?/;

/** Extract the bare "21.A.XX" article code from a reference_code like "GM 21.A.91". */
export function articleCode(ref: string): string {
  const m = ref.match(ARTICLE_RE);
  return m ? m[0] : ref;
}

/** Sort IR before AMC before GM, then by reference_code. */
function typeOrder(t: string): number {
  return { IR: 0, AMC: 1, GM: 2, CS: 3 }[t as "IR" | "AMC" | "GM" | "CS"] ?? 9;
}

/** Sort article codes like 21.A.91 naturally, not lexicographically. */
function compareArticleCodes(a: string, b: string): number {
  const na = parseInt(a.split(".").pop()?.replace(/[A-Z]/g, "") ?? "0", 10);
  const nb = parseInt(b.split(".").pop()?.replace(/[A-Z]/g, "") ?? "0", 10);
  if (na !== nb) return na - nb;
  return a.localeCompare(b);
}

/**
 * Group a flat list of nodes into Subpart → Article → [nodes].
 * Subparts are detected from the penultimate segment of hierarchy_path
 * (the last segment being the node's own leaf).
 */
export function buildTree(nodes: NodeSummary[]): SubpartGroup[] {
  const bySubpart = new Map<string, Map<string, NodeSummary[]>>();

  for (const node of nodes) {
    const parts = node.hierarchy_path.split(" / ");
    // Last segment is the node's own leaf name; the one before it is the subpart.
    const subpart = parts.slice(0, -1).find((p) => /^\(?SUBPART/i.test(p)) ?? "Other";
    const art = articleCode(node.reference_code);

    if (!bySubpart.has(subpart)) bySubpart.set(subpart, new Map());
    const bucket = bySubpart.get(subpart)!;
    if (!bucket.has(art)) bucket.set(art, []);
    bucket.get(art)!.push(node);
  }

  const result: SubpartGroup[] = [];
  for (const [subpartName, articles] of bySubpart) {
    const articleGroups: ArticleGroup[] = [];
    for (const [code, nodes] of articles) {
      nodes.sort((a, b) => {
        const to = typeOrder(a.node_type) - typeOrder(b.node_type);
        if (to !== 0) return to;
        // Within same type: Appendix nodes come after regular nodes
        const aApp = a.reference_code.startsWith("Appendix") ? 1 : 0;
        const bApp = b.reference_code.startsWith("Appendix") ? 1 : 0;
        if (aApp !== bApp) return aApp - bApp;
        return a.reference_code.localeCompare(b.reference_code);
      });
      articleGroups.push({ articleCode: code, nodes });
    }
    articleGroups.sort((a, b) => compareArticleCodes(a.articleCode, b.articleCode));
    result.push({ name: subpartName, articles: articleGroups });
  }

  result.sort((a, b) => a.name.localeCompare(b.name));
  return result;
}
