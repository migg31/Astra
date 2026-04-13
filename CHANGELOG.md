# Changelog

All notable changes to Astra will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-04-13

### Added
- **Image rendering**: Images embedded in Flat-OPC XML documents (Part 21, CS-ACNS, CS-25) are now extracted as base64 data-URIs and rendered inline in the article viewer.
- **Em-dash list grouping**: Paragraphs starting with `—` (em-dash) in the article HTML are now grouped into indented `<ul>` lists, matching the original PDF layout.
- **`bullet1`/`bullet2` Word styles**: Word paragraph styles `bullet1`, `bullet2` etc. were not recognized as list items — now correctly rendered as `<li>` elements in `<ul>`.
- **Stale node deletion**: Re-ingestion now removes nodes from the database that are no longer present in the source document.

### Fixed
- **Parser regression — `AMC N ARTICLE` pattern**: Titles like `"AMC 1 ACNS.C.PBN.305"` (space between type and variant number) were parsed with code `"1"` instead of `"ACNS.C.PBN.305"`. Fixed by supporting spaced variant numbers in `TITLE_RE` with a lookahead to avoid ambiguity with numeric article codes.
- **Parser regression — `GM 21.A.101`**: `GM\s*\d*` was greedily consuming the first digit of numeric article codes (e.g. `"GM 21.A.101"` → code `"1.A.101"`). Fixed with a lookahead-guarded alternative.
- **Parser regression — `GM No N to ARTICLE`**: `"GM No 1 to 21.A.101(g)"` was not matched by the `No.` prefix pattern (AMC-only). Extended to cover GM as well.
- **Duplicate CS/AMC appendix nodes**: Added a third pass in the parser to drop spurious `CS`-typed appendix nodes when an `AMC`/`GM` counterpart with the same `reference_code` exists in the same batch.
- **ACNS appendix isolation**: CS-ACNS appendices were appearing as isolated tree nodes. Root cause was the `AMC 1 ACNS.C.PBN.305` mis-parse; fixed by the `TITLE_RE` correction above.

### Changed
- **`pyproject.toml`**: Removed unused `chromadb` and `pymupdf` dependencies.
- **Non-regression discipline**: Any change to `TITLE_RE` or `_classify` must be validated with targeted test cases and a full scan of all source XMLs before ingestion.

### Removed
- `scratch/` directory (one-off diagnostic scripts).
- `scripts/cleanup_cs_duplicates.py`, `scripts/reset_cs_sources.py` (one-shot migration scripts, no longer needed).
- `Plan.MD`, `RAG.MD`, `RAG2.MD` (internal working documents).

## [0.5.0] - 2026-04-12

### Added
- **Version History drawer**: Collapsible panel pinned to the bottom of the left sidebar, replacing the modal overlay. Shows a flat dense list (changelog style) of all known amendments/editions per document, with badges (indexed, latest, XML, node count, not-latest warning) and a download link with confirmation dialog before triggering EASA PDF download.
- **Resizable left panel**: Drag handle on the right edge of the sidebar allows resizing between 180px and 520px.
- **NeighborsPanel sorting**: Relation groups now ordered by priority (IMPLEMENTS → ACCEPTABLE_MEANS → GUIDANCE_FOR → REQUIRES → REFERENCES); items within each group sorted by node type (IR → AMC → GM → CS).

### Changed
- **Version History UI**: Replaced timeline/vertical-connector layout with a flat dense list (`dhl-*` components). Each row: INDEXED chip · version label · badges · date · ↗ download button.
- **History trigger**: Moved from a standalone button in the main bandeau to a collapsible drawer at the bottom of the TreePanel. Header always visible, collapses to header-only height when closed and sticks to the bottom of the panel.
- **Type pills**: Removed from article header title band and from meta-line — information is already present in the NeighborsPanel.
- **Node history button**: Removed from ArticlePanel (unused feature).
- **Language enforcement**: All UI labels and code are now strictly English throughout the codebase.

### Fixed
- **CORS**: Added PATCH, DELETE, OPTIONS to allowed methods in FastAPI CORS middleware.
- **Harvester `enabled` flag**: Ingestion now correctly skips sources with `enabled=False`.
- **Download confirmation**: EASA links now prompt for confirmation before triggering browser download.

### Removed
- Debug scripts: `check_catalog.py`, `check_patterns.py`, `check_schema.py`, `check_titles.py`, `watch_harvest.py`.
- `mockup-history.html` (temporary design mockup).

## [0.4.0] - 2026-04-12

### Added
- **DocPicker**: Rich document selector dropdown integrated at the top of the sidebar, replacing the flat horizontal DocStrip. Displays the full EASA Regulatory Framework organized by domain (Initial Airworthiness, Continuing Airworthiness, Air Operations, Aircrew, Aerodromes) with color-coded section headers and node counts per indexed document.
- **Doc Info Page**: When no article is selected (or on first load after switching document), `ArticlePanel` now renders a document overview page showing domain, short name, full name, description, version, publication date, and a link to the EASA website.
- **Auto-select on document switch**: Switching document via the DocPicker now automatically selects the first IR node of the new document, ensuring the article panel is never stale.
- **Catalog shared state**: `getCatalog()` is now fetched once in `App` and passed as a prop to `NavigatePanel`, `TreePanel` (DocPicker), and `ArticlePanel` — eliminating duplicate API calls.

### Changed
- **Consult layout**: Removed the `DocStrip` horizontal tab bar. The 3-column grid (`TreePanel` / `ArticlePanel` / `NeighborsPanel`) now renders directly under the topbar.
- **NavigatePanel**: Removed internal `getCatalog()` fetch — now receives `catalog` as a prop from `App`.
- **NeighborsPanel v2**: Redesigned with collapsible relation groups (▼/▶), color-coded relation badges (`Implements`, `Acceptable Means`, `Guidance`, `References`, `Requires`…), and directional icons (↗ outgoing / ↙ incoming).
- **TreePanel**: Document selector removed from sidebar — replaced by DocPicker at the top.

### Removed
- `DocStrip.tsx` component (superseded by DocPicker inside TreePanel).

## [0.3.0] - 2026-04-12

### Added
- **Multi-Source Harvester**: Support for multiple EASA regulatory packages — CS-25 (Large Aeroplanes) and CS-ACNS (Communications, Navigation & Surveillance) fully ingested.
- **Versioning Foundation**: Added `version_label` to document tracking and automated version extraction (Revision/Issue/Amendment) from EASA XML sources.
- **Dynamic Source Selection**: Interactive source selector in the Admin Console to trigger specific regulatory updates.
- **Two-Level Explorer Tree**: `Subpart → Section → Article` hierarchy for CS-ACNS; CS-25 remains `Subpart → Article`. Sections are collapsible sub-headers.
- **Collapsed-by-default Tree**: Explorer tree resets to fully collapsed state on each document selection.

### Fixed
- **CS-25 AMC reference codes**: `TITLE_RE` prefix regex `AMC\s*\d*` was absorbing leading digits of article codes (e.g. `AMC 25.1301` parsed as prefix `AMC 2` + code `5.1301`). Fixed to `AMC\d*` (no space before digit).
- **Variant extraction false positives**: `_build_reference_code` incorrectly treated the article number as a variant number (e.g. `AMC 25` → variant `25`). Fixed lookahead to require the digit be followed by a space/end, not a dot.
- **CS-ACNS subpart hierarchy**: `_heading_level` had `SECTION < SUBPART` ordering inverted — Sections (level 2) were overwriting Subpart context in the heading stack. Swapped to `SUBPART=2, SECTION=3` so hierarchy paths now correctly include `Subpart B / Section 1 / …`.
- **AMC→CS edge building**: Edge resolution was calling `re.search(ARTICLE_CODE_PATTERN, reference_code)` on the full reference code, matching the `AMC` prefix token instead of the article code. Now strips the type prefix first and falls back to stripping sub-paragraph refs `(a)(2)` to find the parent article.
- **Explorer node truncation**: `listAllNodes()` used `limit=5000` while the DB had grown to 5 495 nodes — subparts E–J of CS-25 were silently dropped. Limit raised to `10 000`.

### Improved
- **Generic Ingestion Pipeline**: Refactored `easa_fetcher` and `ingest` logic to handle any "Easy Access Rules" XML package.
- **Data Granularity**: Separate storage paths for raw data, organized by source and fetch date.
- **CS-25 edges**: 2 293 edges inserted (up from 2 286 before the AMC reference-code fix).
- **CS-ACNS edges**: 311 edges inserted (up from 56 before the edge-building fix).
- **`buildTree` in `tree.ts`**: Refactored into `Subpart → Section → Article` with helper functions `sortArticles` / `sortNodes`; `SubpartGroup` now carries both `sections[]` and a flat `articles[]` for search and leaf counts.

## [0.2.0] - 2026-04-11

### Added
- **Admin Console (UI)**: New slide-over control panel accessible via the ⚙️ icon in the topbar.
- **System Health Monitoring**: Real-time connectivity status for PostgreSQL, ChromaDB, and Ollama.
- **AI Model Verification**: Specific checks for `mistral` (chat) and `nomic-embed-text` (embedding) models on Ollama server.
- **Live Statistics**:
    - **Regulatory Inventory**: Document, Node, and Edge counts.
    - **Storage Metrics**: SQL database size and Vector database file size on disk.
    - **AI Status**: Total embeddings generated.
- **Interactive Harvester**: Trigger EASA Part 21 synchronization directly from the UI with background task execution.
- **Source Configuration**: Expandable section showing current regulatory sources and download URLs.

### Improved
- **Harvester Reliability**: Updated `User-Agent` to avoid HTTP 429 errors from EASA servers.
- **UI Architecture**: Compacted vertical layout for better usability on standard displays.
- **Visual Polish**: Tree-style health indicators with perfect CSS-drawn connectors and categorized stat cards with icons.
- **API Routing**: Harmonized admin endpoints under `/api/admin/`.

### Fixed
- **404 Errors**: Corrected API prefixing for admin routes.
- **UI Alignment**: Fixed vertical gaps in health status hierarchy and centered text alignment with tree symbols.

---

## [0.1.0] - 2026-04-11

### Added
- **Initial Proof of Concept release** of Astra, an aviation Type Certification expertise platform for EASA Part 21 professionals
- **HARVEST Module** - Automated regulatory data collection infrastructure
  - EASA Easy Access Rules scraper (Part 21, CS-25)
  - HTML to structured data conversion pipeline
  - Document versioning and change detection system
- **Database Layer** - PostgreSQL-based knowledge graph storage
  - Regulatory nodes model (IR, AMC, GM, CS)
  - Regulatory edges model with 10 relation types
  - Schema for harvest sources and document tracking
- **API Backend** - FastAPI REST API
  - Health check endpoints (`/health`, `/db/ping`)
  - Node retrieval and search endpoints
  - Graph traversal capabilities
  - CORS support for frontend integration
- **Development Infrastructure**
  - Docker Compose setup for PostgreSQL (port 5433)
  - Python 3.12+ with uv package management
  - pytest test framework with async support
  - Ruff linting configuration
- **Frontend Skeleton** - React/TypeScript setup
  - Vite build system
  - API client configuration
  - Development server on localhost:5173

### Technical Details
- **Backend Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0, AsyncPG, Pydantic
- **Database**: PostgreSQL with planned ChromaDB integration for vector search
- **Frontend**: React, TypeScript, Vite (development scaffold only)
- **Testing**: pytest with async support, httpx for API testing
- **Code Quality**: Ruff linting, line length 100, Python 3.12 target

### Scope - Phase 1 PoC
- **Regulatory Coverage**: EASA Part 21 Subparts B & D (Type Certificates & Changes)
- **Knowledge Graph**: 500+ regulatory nodes, 1000+ relationships target
- **Change Detection**: Functional for EASA sources (NPAs, Opinions, ED Decisions)
- **User Interface**: EXPLORE module prototype for regulatory navigation

### Limitations
- No business logic yet - infrastructure foundation only
- Frontend UI not implemented (scaffold only)
- No RAG/LLM integration (planned for Phase 2)
- No authentication or multi-tenancy (planned for Phase 3)
- Standards paywalled handling not implemented
- Subpart G (Production) coverage limited to interface references

### Documentation
- Comprehensive design document (`Plan.MD`) with full system architecture
- API documentation via FastAPI auto-generated docs
- Database schema documentation in models
- Setup and run instructions in README.md

### Next Steps (Phase 2 - MVP)
- FAA sources integration
- RAG engine with ChromaDB
- ASK assistant with anti-hallucination safeguards
- LEARN module with structured learning paths
- PRACTICE scenarios for change classification
- Enhanced frontend with full UI implementation
