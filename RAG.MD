# Astra RAG Improvement Plan

Objective: Enhance the precision, recall, and contextual depth of the EASA regulatory assistant.

---

## PART A: Current Architecture Improvements & Implementation Plan

### 1. Implementation Roadmap
1. **Short Term (Phase 1):** Data Quality & Logic. Implementing **[5]** (Recursive Chunking), **[6]** (Parent-Child linking), and **[9]** (Breadcrumb injection).
2. **Medium Term (Phase 2):** Infrastructure Upgrade. Migrating from **[1]** to **[2]** (PGVector) to enable hybrid search and tighter relational integration.
3. **Long Term (Phase 3 & 4):** Advanced Retrieval. Integrating **[13]** (Cohere Rerank) and implementing Context Neighbors for full article reconstruction.

---

### 2. Phase 1: Semantic Indexing & Versioning (Data Quality)
**Goal:** Improve vector "scoping" and ensure data freshness.

*   **Version Filtering:** Update `_fetch_nodes` to only index nodes where `is_latest = true`. This ensures the assistant doesn't cite deprecated regulations.
*   **Breadcrumb Injection [9]:** Format: `[Source] > [Path] > [Title] \n\n [Content]`. This encodes the hierarchy directly into the vector, improving semantic matching for localized queries.
*   **Recursive Chunking [5]:** Replace fixed truncation **[4]** with a splitter that respects paragraph (`\n\n`) and list boundaries.
*   **Parent-Child Logic [6]:** Index small fragments (Children) for high-precision retrieval, but link them to their original full nodes (Parents) for generation.

**Files to Modify:** `backend/rag/ingest_embeddings.py`, `backend/rag/store.py`.

---

### 3. Phase 2: Hybrid Search (Vector + SQL FTS)
**Goal:** Capture exact references (e.g., "AMC 21.A.101") that vector search might miss.

*   **Storage Migration:** Move from **[1]** (ChromaDB) to **[2]** (PGVector).
*   **Dual Retrieval:** Execute Semantic Query (Vector) and Lexical Query (Postgres FTS) in parallel.
*   **RRF Fusion:** Implement Reciprocal Rank Fusion to merge and score results from both engines.

**Files to Modify:** `backend/database/models.py`, `backend/rag/store.py`, `backend/rag/responder.py`.

---

## PART B: Technical Solutions & Strategic Evaluations

### 1. Technical Solutions Registry
| ID | Solution Name | Description | Architectural Impact | Benefit |
| :--- | :--- | :--- | :--- | :--- |
| **[1]** | **ChromaDB** | Local vector DB (Current). | **None** (Baseline). | Fast for MVP. |
| **[2]** | **PGVector** | PostgreSQL vector extension. | **High:** Update Docker, rewrite `store.py`. | **Single Source of Truth.** |
| **[3]** | **Pinecone** | Managed vector DB. | **Medium:** Add API client, update `.env`. | Zero maintenance. |
| **[4]** | **Fixed** | 2k char truncation (Current). | **None** (Baseline). | Baseline speed. |
| **[5]** | **Recursive** | Smart text splitting. | **Low:** Add text-splitter dependency. | No broken sentences. |
| **[6]** | **Parent-Child** | Retrieval linking. | **Medium:** New DB columns & query logic. | **High Precision + Context.** |
| **[7]** | **Agentic** | LLM-driven splitting. | **High:** Complex ingestion pipeline. | Highest quality. |
| **[8]** | **Raw** | Direct query (Current). | **None** (Baseline). | Lowest latency. |
| **[9]** | **Rewriting** | Metadata extraction. | **Low:** New LLM call in `responder.py`. | **Auto-detects EASA codes.** |
| **[10]**| **HyDE** | Hypothetical answers. | **Medium:** Double LLM pipeline. | Bridges semantic gap. |
| **[11]**| **Cross-Encoder**| Local reranker. | **Medium:** New local model weights to host. | High accuracy boost. |
| **[12]**| **LLM-Ranker** | Zero-shot ranking. | **Low:** New prompt logic in `responder.py`. | Flexible/Simple. |
| **[13]**| **Cohere Rerank**| Managed reranking API. | **Low:** Add cohere client & API key. | **Elite accuracy** on regs. |

---

### 2. Detailed Solution Benefits
- **[2] PGVector:** Enables complex SQL joins (e.g., filtering by `is_latest`) in the same query as vector search, ensuring perfect data consistency.
- **[6] Parent-Child:** Allows the system to find the exact "needle" (specific sentence) but give the LLM the whole "haystack" (article) for a complete answer.
- **[9] Query Rewriting:** Automatically detects mentions of specific codes (e.g., "CS-25") to apply hard SQL filters, drastically reducing noise.
- **[13] Cohere Rerank:** Provides superior precision on public domain technical/legal text where specific terminology is critical.

---

### 3. Benchmarking & Strategic Decisions

| Solution Component | Relevance | Latency | Complexity | Cost (Tokens) | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Storage: [2]** | High | Medium | Medium | $0 | **Best for Production** |
| **Chunking: [6]** | High | Medium | High | $0 | **Essential for Context**|
| **Query Opt: [9]** | High | Medium | Medium | Low | **Best ROI** |
| **Reranking: [13]** | Elite | Medium | Low | Low (API) | **Best Accuracy** |

**Final Strategy:** Since EASA documents are public domain and privacy is not a constraint, the focus is on **maximum relevance and ease of maintenance**. Use **[2]** (PGVector) for data integrity, **[6]** (Parent-Child) for context, and **[13]** (Cohere Rerank) for maximum precision.
