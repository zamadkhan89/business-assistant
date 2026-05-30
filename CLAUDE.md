# CLAUDE.md — Business Assistant

Read MASTER_PROMPT.md first. This file is the short project reference.

## What this is
Multi-agent conversational analytics: natural language → schema linking → SQL → HITL approval → chart.
Four agents: Supervisor, Schema, SQL, Analysis. Built with LangGraph + FastAPI + Next.js.
Post-defense additions: AWS Athena integration, saved queries, daily routines, multi-user isolation, table metadata, admin system.

## Stack at a glance
| Layer | Tech |
|---|---|
| Backend | FastAPI, Python 3.11+, async |
| Agents | LangGraph, LangChain |
| LLM | Anthropic Claude via `init_chat_model()` |
| Primary DB | PostgreSQL (asyncpg) — SQLite for dev/tests |
| Analytical DB | DuckDB (in-process) |
| Cloud analytics | AWS Athena (optional, boto3) |
| Vector store | ChromaDB (local ephemeral) |
| Frontend | Next.js 14 App Router, Tailwind v4, shadcn/ui, NextAuth v5 |

## Running locally
```powershell
cd backend
.venv\Scripts\Activate.ps1
python -m pytest                       # all tests (uses MemorySaver + SQLite in-memory)
uvicorn app.main:app --reload          # dev server on :8000 (MemorySaver fallback on Windows)
```

PostgreSQL 16 is installed locally (postgres/postgres, port 5432, DB: business_assistant).
`DATABASE_URL` and `POSTGRES_URL` in `backend/.env` point to it.
On Windows: uvicorn uses ProactorEventLoop → psycopg3 async falls back to MemorySaver;
SQLAlchemy (asyncpg) still uses PostgreSQL for user/thread/message data.

## Key files
- [backend/app/core/config.py](backend/app/core/config.py) — all settings via env vars (incl. ADMIN_EMAILS, QUERY_TIMEOUT_SECONDS)
- [backend/app/core/llm.py](backend/app/core/llm.py) — single LLM entrypoint, never import provider SDK elsewhere
- [backend/app/core/db.py](backend/app/core/db.py) — SQLAlchemy engine + Base + get_db
- [backend/app/agents/graph.py](backend/app/agents/graph.py) — StateGraph + checkpointer wiring
- [backend/app/agents/state.py](backend/app/agents/state.py) — shared TypedDict state (incl. query_engine, athena_creds, preloaded_metadata)
- [backend/app/agents/supervisor.py](backend/app/agents/supervisor.py) — keyword-based intent routing
- [backend/app/api/chat.py](backend/app/api/chat.py) — POST /chat, POST /chat/resume; pre-loads glossary + Athena creds + metadata before ainvoke
- [backend/app/api/saved_queries.py](backend/app/api/saved_queries.py) — save/list/delete/run queries inline
- [backend/app/api/routines.py](backend/app/api/routines.py) — routine CRUD + run all questions through LangGraph
- [backend/app/api/athena.py](backend/app/api/athena.py) — Athena config, table listing, ingest, direct query registration
- [backend/app/api/catalog.py](backend/app/api/catalog.py) — table + column metadata (descriptions, KPIs, join hints) — routes at `/api/catalog/*`
- [backend/app/data/duckdb_connector.py](backend/app/data/duckdb_connector.py) — DuckDB I/O, _dataset_ownership, _next_versioned_name

## Environment
- **Dev**: `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/business_assistant`
- **LangGraph checkpointer**: `POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/business_assistant` (falls back to MemorySaver on Windows)
- **Tests**: SQLite in-memory + MemorySaver, auto-configured via `tests/conftest.py`
- **LLM key**: `ANTHROPIC_API_KEY` in `backend/.env`
- **Admin**: `ADMIN_EMAILS=email1@example.com,email2@example.com` — grants global Athena config access

## Windows asyncio rule
**Never call `asyncio.run()` or async DB operations inside LangGraph nodes on Windows.**
All PostgreSQL data needed by agent nodes (glossary, Athena creds, table metadata) must be pre-loaded in the async FastAPI endpoint handler and passed as initial state fields to `graph.ainvoke()`.

## Multi-user isolation rules
- Schema agent must call `describe_user_tables(user_id)` — never `describe_all_tables()`
- ChromaDB searches must include `where={"user_id": user_id}` metadata filter
- Every new data layer (caching, vector index, object store) must scope to `user_id` immediately

## Conventions
- All LLM calls through `get_llm()` in `app/core/llm.py`
- SQL generation: `temperature=0.0`; summaries: `temperature=0.3`
- Tests: `pytest-asyncio`, `asyncio_mode=auto`, `httpx.AsyncClient`
- Commits: `feat:` / `fix:` / `docs:` / `test:` / `refactor:` / `chore:`
- Tailwind v4: use `bg-linear-to-br` not `bg-gradient-to-br`; use `w-150` not `w-[600px]`

## Security rules
- Passwords: bcrypt, cost factor 12
- JWT: HS256, 24h expiry, secret from env
- SQL validation: hard-reject DROP/DELETE/UPDATE/TRUNCATE/INSERT/ALTER/GRANT/REVOKE
- Never log JWT tokens or full prompts containing user data
- Ownership check on every endpoint: `if not r or r.user_id != current_user.id: raise 404`
