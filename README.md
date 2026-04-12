# Astra (v0.3.0)

Aviation Type Certification expertise platform for EASA Part 21 professionals.

## Phase 2 MVP — In Progress

Full-stack application covering HARVEST, EXPLORE, and **ASK (RAG)** layers.

| Layer | Status | Detail |
|---|---|---|
| HARVEST | ✅ | EASA XML parser — Part 21 + CS-25 (836 nodes) + CS-ACNS (501 nodes) |
| DATA | ✅ | PostgreSQL (Structured) + ChromaDB (Vector) |
| KNOWLEDGE | ✅ | 5 495+ regulatory nodes (IR / AMC / GM / CS), 2 600+ edges |
| EXPLORE UI | ✅ | React 3-panel: tree (Subpart → Section → Article) / article / neighbors |
| ASK UI | ✅ | RAG-based AI assistant with anti-hallucination safeguards |
| ADMIN | ✅ | Admin Console for system health, stats, and harvester control |

### Key Features
- **Admin Console**: Real-time monitoring of PostgreSQL, ChromaDB, and Ollama (Mistral/Nomic).
- **Interactive Harvester**: Trigger regulatory sync directly from the UI.
- **Regulatory Explorer**: Tree navigation with full HTML rendering and clickable cross-references.
- **AI Assistant**: Query Part 21 using natural language with strict sourcing and disclaimers.

## Prerequisites

- Python 3.12+
- Docker Desktop (for Postgres & ChromaDB)
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
# 2. Generate Vector Embeddings (Requires Ollama running)
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
    ├── components/   ArticlePanel, TreePanel, NeighborsPanel
    ├── api.ts        HTTP client
    ├── tree.ts       Tree grouping logic
    └── types.ts      TypeScript interfaces
```

## Notes

- Postgres host port: **5433** (5432 reserved for other local projects)
- EASA XML format: Flat OPC (Word document packaged as `pkg:package` XML)
- Content stored as both plain text and HTML; images embedded as base64 data-URIs
