# CertifExpert

Aviation Type Certification expertise platform for EASA Part 21 professionals.

## Phase 1 PoC — current scope

Foundational infrastructure and the HARVEST/KNOWLEDGE data model. No business
logic yet — scrapers, graph traversal, and the EXPLORE UI are built on top of
this skeleton in later sessions.

See `Plan.MD` for the full design document.

Host Postgres port is **5433** (5432 reserved for other projects).

## Prerequisites

- Python 3.12+
- Docker Desktop (for the Postgres container)
- `uv` (`pip install uv`; invoke as `python -m uv` if not on PATH)

## Setup

```bash
cp .env.example .env
python -m uv sync
docker compose up -d postgres
docker exec -i certifexpert-db psql -U certifexpert -d certifexpert \
  < backend/database/migrations/001_initial_schema.sql
```

## Run

```bash
python -m uv run uvicorn backend.api.main:app --reload
# http://localhost:8000/health
# http://localhost:8000/db/ping
```

## Test

```bash
python -m uv run pytest -q
```
