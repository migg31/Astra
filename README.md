# Astra (v0.6.0)

Aviation Certification platform for EASA regulatory framework.

## Phase 2 MVP — In Progress

Full-stack application covering HARVEST, EXPLORE, and **ASK (RAG)** layers.

| Layer | Status | Detail |
|---|---|---|
| HARVEST | ✅ | EASA XML parser — Part 21 (1 095 nodes) + CS-25 + CS-ACNS (503 nodes) |
| DATA | ✅ | PostgreSQL + pgvector (Vector) |
| KNOWLEDGE | ✅ | 5 500+ regulatory nodes (IR / AMC / GM / CS), 2 600+ edges |
| EXPLORE UI | ✅ | React 3-panel: resizable sidebar / article / neighbors — with version history drawer |
| ASK UI | ✅ | RAG-based AI assistant with anti-hallucination safeguards |
| ADMIN | ✅ | Admin Console for system health, stats, and harvester control |

### Key Features
- **Admin Console**: Real-time monitoring of PostgreSQL, pgvector, and Ollama (Mistral/Nomic).
- **Interactive Harvester**: Trigger regulatory sync directly from the UI with `enabled` flag support.
- **Regulatory Explorer**: DocPicker sidebar (EASA framework by domain), resizable tree panel, HTML article rendering with clickable cross-references, and a doc info page on first load.
- **Version History drawer**: Flat dense list of all amendments/editions pinned to the bottom of the sidebar, collapsible, with EASA download links (with confirmation).
- **Neighbors Panel v2**: Collapsible relation groups sorted by priority (IR→AMC→GM→CS), color-coded badges.
- **AI Assistant**: Query Part 21 using natural language with strict sourcing and disclaimers.

## Prerequisites

- Python 3.12+
- Docker Desktop (for Postgres)
- `uv` (`pip install uv`)
- Node.js 18+ (for the frontend)
- **Ollama** (Running locally with `mistral` and `nomic-embed-text` models)

## Setup

```bash
cp .env.example .env

# Python deps
python -m uv sync

# Start Infrastructure
docker compose up -d

# Apply PostgreSQL migrations
# (Run scripts in backend/database/migrations/ 001 to 004)

# Initial Ingestion & Embedding
# 1. Fetch & Parse XML
python -m uv run python -m backend.harvest.ingest
# 2. Generate Vector Embeddings (optional — requires Ollama running)
python -m uv run python -m backend.rag.ingest_embeddings
```

## Run

```bash
# Backend
python -m uv run uvicorn backend.api.main:app --reload
# → http://localhost:8000/api/admin/health

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

## Admin Console
Click the ⚙️ **CONSOLE** button in the topbar to access:
- **System Health**: Connection status to all backends.
- **Statistics**: Inventory of documents, nodes, and database sizes.
- **Regulatory Sources**: View current EASA source URLs.
- **Harvester Control**: Run the ingestion pipeline and view live logs.

## Test

```bash
python -m uv run pytest -q
```

## Architecture

```
backend/
├── api/          FastAPI — REST endpoints (/api/nodes, detail, neighbors)
├── database/     SQLAlchemy models + Postgres migrations
├── harvest/      EASA XML fetcher, parser, HTML converter, ingest CLI
└── tests/        Schema smoke tests + API integration tests

frontend/
└── src/
    ├── components/   ArticlePanel, TreePanel (DocPicker), NeighborsPanel, NavigatePanel
    ├── api.ts        HTTP client
    ├── tree.ts       Tree grouping logic
    └── types.ts      TypeScript interfaces
```

## Notes

- Postgres host port: **5433** (5432 reserved for other local projects)
- EASA XML format: Flat OPC (Word document packaged as `pkg:package` XML)
- Content stored as both plain text and HTML; images embedded as base64 data-URIs
