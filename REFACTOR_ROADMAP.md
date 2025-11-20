# Refactor Roadmap ✅💥

> Elite CTO Mode: Full-system modernization executed in phases. Each task must reach production-grade quality with bilingual docs and exhaustive testing.

## Phase 1 – Audit & Purge
- [x] P1.1 Deep scan every path, config, and asset.
- [x] P1.2 Delete/Archive dead code, unused imports, commented legacy blocks.
- [x] P1.3 Relocate hardcoded secrets into `.env` + sanitize `.env.example`.
- [x] P1.4 Document critical anti-patterns (security order, SQLite usage, tight LLM coupling, Ollama concurrency limits).

## Phase 2 – Architectural Surgery
- [x] P2.1 Replace every SQLite usage with PostgreSQL (async SQLAlchemy/Tortoise).
- [x] P2.2 Enforce schema isolation per microservice.
- [x] P2.3 Reorder FastAPI middleware pipeline: `RateLimit -> SecurityHeaders -> JWT Auth -> Pydantic`.
- [x] P2.4 Decouple LLM service via internal HTTP APIs (no direct DB/vector access).
- [ ] P2.5 Modularize frontend (Streamlit/React) per modern component standards.

## Phase 3 – Vibe Coding Standards
- [x] P3.1 Apply strict type hints + PEP8/Prettier formatters.
- [x] P3.2 Add bilingual (EN/AR) docstrings to every function/class.
- [x] P3.3 Rewrite Markdown docs (README, CONTRIBUTING, architecture) with emojis, badges, and clear sections.

## Phase 4 – Testing & Forensics
- [x] P4.1 Extract and secure default admin credentials into `SECURE_ADMIN_CREDS.json` (gitignored).
- [x] P4.2 Simulate login using extracted admin creds.
- [x] P4.3 Build pytest suite for critical path (Login → Upload Doc → RAG Query) with mocked LLM calls.
- [ ] P4.4 Achieve 100% test coverage threshold gate. (Deferred - requires additional test cases)

## Phase 5 – Visualization & Reporting
- [x] P5.1 Convert legacy diagrams into Mermaid.js blocks inside `ARCHITECTURE.md`.
- [x] P5.2 Author `graph TD` for system architecture (Postgres-centered).
- [x] P5.3 Author `sequenceDiagram` for auth flow (correct middleware order).
- [x] P5.4 Deliver final `REFACTOR_REPORT.md` summarizing outcomes + lessons learned.

---

Progress updates must keep this roadmap synchronized. No box is checked without a completed, reviewed deliverable.

