# Astra

Aviation Type Certification expertise platform for EASA Part 21 professionals.

## Phase 1 PoC — completed

Full-stack working prototype covering the HARVEST and EXPLORE layers.

| Layer | Status | Detail |
|---|---|---|
| HARVEST | ✅ | EASA Easy Access Rules XML parser — Part 21 Subparts B, D, E, G, J |
| DATA | ✅ | PostgreSQL schema (HARVEST + KNOWLEDGE domains) |
| KNOWLEDGE | ✅ | 103 regulatory nodes (IR / AMC / GM), 139 edges |
| EXPLORE UI | ✅ | React 3-panel: tree / article / neighbors |

### What works
- Regulatory tree grouped by Subpart → Article → variants (IR / AMC / GM / Appendix)
- Full HTML rendering of EASA content (tables, images, bold/italic, indentation)
- Visual design matching EASA online publication (color codes IR/AMC/GM)
- Clickable cross-references: `21.A.XX` navigates to the target node; `21.B.XX` highlighted as non-navigable mentions
- Search bar filtering across reference codes and titles
- Article header: colored band (type-specific), applicability date, regulatory source

## Prerequisites

- Python 3.12+
- Docker Desktop (for the Postgres container)
- `uv` (`pip install uv`)
- Node.js 18+ (for the frontend)

## Setup

```bash
cp .env.example .env

# Python deps
python -m uv sync

# Start Postgres
docker compose up -d postgres

# Apply migrations
docker exec -i certifexpert-db psql -U certifexpert -d certifexpert \
  < backend/database/migrations/001_initial_schema.sql
docker exec -i certifexpert-db psql -U certifexpert -d certifexpert \
  < backend/database/migrations/002_add_content_html.sql
docker exec -i certifexpert-db psql -U certifexpert -d certifexpert \
  < backend/database/migrations/003_add_regulatory_source.sql
docker exec -i certifexpert-db psql -U certifexpert -d certifexpert \
  < backend/database/migrations/004_add_dates.sql

# Ingest EASA Part 21 (downloads ~15 MB ZIP from easa.europa.eu)
python -m uv run python -m backend.harvest.ingest

# Or offline if already downloaded:
python -m uv run python -m backend.harvest.ingest --offline data/raw/easa/<date>/part21.xml
```

## Run

```bash
# Backend
python -m uv run uvicorn backend.api.main:app --reload
# → http://localhost:8000/health
# → http://localhost:8000/api/nodes

# Frontend (separate terminal)
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

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
