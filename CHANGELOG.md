# Changelog

All notable changes to CertifExpert will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-04-11

### Added
- **Initial Proof of Concept release** of CertifExpert, an aviation Type Certification expertise platform for EASA Part 21 professionals
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

---

## [Unreleased]
