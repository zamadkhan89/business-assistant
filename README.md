# Business Assistant

A multi-agent conversational analytics system that lets non-technical users query business data in plain English, with human review of every SQL query before it executes.

## Three core differentiators

| # | What | Why it matters |
|---|------|---------------|
| 1 | **Schema linking with embeddings** | Picks the right tables from a large schema using ChromaDB semantic search instead of dumping the entire schema into the prompt |
| 2 | **Business glossary** | User-defined terms ("revenue = net of returns") stored in Postgres and injected into every SQL generation prompt automatically |
| 3 | **Human-in-the-loop SQL approval** | Every generated query pauses for user review using LangGraph's `interrupt()` primitive — approve, edit, or reject before execution |

## Full flow

```
Browser
  │
  ▼
POST /api/chat
  │
  ▼
LangGraph StateGraph
  │
  ├─► Supervisor node ──keyword routing──► Schema Agent
  │                                              │
  │                                         ChromaDB (semantic table search)
  │                                              │
  │                                         SQL Agent
  │                                              │
  │                                    [interrupt() — waits for decision]
  │                                              │
  │                                   POST /api/chat/resume
  │                                   (approve / edit / reject)
  │                                              │
  │                                        Analysis Agent
  │                                   (execute SQL on DuckDB or Athena,
  │                                    pick chart type,
  │                                    build Plotly JSON,
  │                                    rich LLM summary with stats)
  │                                              │
  └──────────────────────────────────────────────┘
  Response: { content, chart_json, status }
```

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI (Python 3.11+), async |
| Agent orchestration | LangGraph 1.1+ (StateGraph, interrupt/resume) |
| LLM | Anthropic Claude via `langchain-anthropic` (swappable via env) |
| Operational DB | PostgreSQL 16 — users, threads, messages, glossary, routines |
| Analytical DB | DuckDB (in-process) — sample data + CSV uploads |
| Cloud analytics | AWS Athena (optional) — direct query or local ingest modes |
| Vector store | ChromaDB (local ephemeral) — schema embeddings |
| Visualization | Plotly + react-plotly.js |
| Frontend | Next.js 14 App Router, TypeScript, Tailwind CSS v4, shadcn/ui |
| Auth | FastAPI JWT (HS256) + NextAuth credentials provider |

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16 (local install, DB: `business_assistant`, user: `postgres`, password: `postgres`)
- An Anthropic API key (set `ANTHROPIC_API_KEY` in `backend/.env`)

## Local setup

### Backend

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Create .env from template and fill in your values
copy .env.example .env

# Verify everything works
python -m pytest          # all tests should pass

# Start the API server
uvicorn app.main:app --reload
# API at http://localhost:8000
# Swagger UI at http://localhost:8000/docs
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
# App at http://localhost:3001
```

### Quick start (both together)

```powershell
# From project root
.\dev.ps1          # starts backend + frontend in separate windows
.\dev.ps1 status   # check both are running
.\dev.ps1 stop     # stop both
```

### Environment variables

Copy `backend/.env.example` to `backend/.env` and set:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL asyncpg URL for SQLAlchemy |
| `POSTGRES_URL` | PostgreSQL URL for LangGraph checkpointer |
| `JWT_SECRET` | Random 32+ char string, shared with frontend |
| `LLM_PROVIDER` | `anthropic` / `google_genai` / `openai` |
| `LLM_MODEL` | e.g. `claude-sonnet-4-6` |
| `ANTHROPIC_API_KEY` | If using Claude (default) |
| `GOOGLE_API_KEY` | If using Gemini |
| `ADMIN_EMAILS` | Comma-separated emails with admin access (optional) |

Copy `frontend/.env.example` to `frontend/.env.local` and set:

| Variable | Description |
|----------|-------------|
| `NEXTAUTH_URL` | Frontend base URL (e.g. `http://localhost:3001`) |
| `NEXTAUTH_SECRET` | Same 32+ char string |
| `NEXT_PUBLIC_BACKEND_URL` | Backend URL (e.g. `http://localhost:8000`) |
| `JWT_SECRET` | Same value as backend |

## Running tests

```powershell
cd backend
python -m pytest -v                           # all unit + integration tests
python -m pytest tests/test_sql_agent.py      # SQL agent only
python -m pytest tests/test_hitl.py           # HITL approval flow only

# Accuracy evaluation (requires LLM key, ~2 min, 20 questions)
python tests/accuracy/run_eval.py
python tests/accuracy/run_eval.py --model claude-sonnet-4-6
```

## Project structure

```
business-assistant/
├── backend/
│   ├── app/
│   │   ├── agents/           # LangGraph nodes
│   │   │   ├── graph.py      # StateGraph wiring
│   │   │   ├── state.py      # AgentState TypedDict
│   │   │   ├── supervisor.py
│   │   │   ├── schema_agent.py
│   │   │   ├── sql_agent.py
│   │   │   └── analysis_agent.py
│   │   ├── api/              # FastAPI routers
│   │   │   ├── auth.py       # signup / login / me
│   │   │   ├── chat.py       # POST /chat, POST /chat/resume
│   │   │   ├── datasets.py   # CSV upload / list / export
│   │   │   ├── glossary.py   # CRUD glossary entries
│   │   │   ├── threads.py    # list threads + messages
│   │   │   ├── saved_queries.py  # save, list, delete, re-run queries
│   │   │   ├── routines.py   # daily routine CRUD + run
│   │   │   ├── athena.py     # Athena config + table management
│   │   │   └── catalog.py        # table + column metadata (descriptions, KPIs)
│   │   ├── core/             # config, db, llm, security
│   │   ├── data/             # DuckDB connector + sample data
│   │   └── models/           # SQLAlchemy models
│   ├── tests/
│   │   ├── accuracy/         # 20-question eval harness
│   │   └── test_*.py         # unit + integration tests
│   ├── Procfile              # Railway deploy
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── home/page.tsx     # redesigned landing page with stats
│   │   ├── chat/page.tsx     # main chat UI with sidebar + glossary badge
│   │   ├── glossary/page.tsx # glossary CRUD
│   │   ├── saved-queries/page.tsx  # inline query runner
│   │   ├── routines/page.tsx # daily routines manager
│   │   └── athena/page.tsx   # Athena data source manager
│   ├── components/
│   │   ├── chat/             # MessageBubble, ChartMessage, CodeBlock
│   │   ├── ThemeProvider.tsx
│   │   └── ThemeToggle.tsx
│   └── lib/auth.ts
├── docs/
│   ├── ARCHITECTURE.md
│   ├── DEMO_SCRIPT.md
│   └── SLIDES.md
├── MASTER_PROMPT.md
└── ONBOARDING.md
```

## Features

### Core analytics
- Ask natural language questions about built-in Northwind e-commerce data
- Upload your own CSV files — same filename creates a new versioned table (`_v2`, `_v3`) rather than replacing
- Review, edit, or reject every generated SQL query before it runs
- See results as interactive Plotly charts (bar / line / scatter, auto-selected)
- Download query results as CSV
- Rich LLM summaries with key findings, statistics (min/max/avg/total), and highlighted patterns

### Data sources
- DuckDB in-process analytical engine for local data and CSV uploads
- AWS Athena integration — connect an S3-backed Athena workspace and query directly from the UI
  - **Ingest mode**: loads Athena tables into DuckDB locally
  - **Direct mode**: schema-only registration, executes queries via Athena (Presto SQL)

### Knowledge management
- Business glossary — user-defined terms injected into SQL generation automatically
- Glossary active indicator in chat: sidebar badge + green banner showing how many terms are applied
- Table metadata editor — add descriptions, KPI definitions, column descriptions, and join hints to improve SQL accuracy

### Productivity tools
- **Saved Queries**: bookmark any result and re-run it inline — see fresh chart and data without returning to chat
- **Daily Routines**: define a named set of questions, run all of them at once, view results side by side

### Platform
- Sign up / log in with JWT-secured accounts (email verification, login rate limiting)
- Dark / light mode toggle
- Browse conversation history in the sidebar
- Admin panel — manage users, storage quotas, block/unblock, audit log, and per-user feature toggles:
  - **Streaming** — enables SSE live step-progress for a user (default: off)
  - **SQL Approval** — requires HITL review before SQL executes (default: off)
- Multi-user privacy isolation — each user's data, uploads, glossary, and Athena config are fully separate

## Security

| Control | Implementation |
|---------|---------------|
| Passwords | bcrypt, cost factor 12 |
| JWT | HS256, 24-hour expiry, secret from env |
| SQL validation | Hard-reject: DROP / DELETE / UPDATE / TRUNCATE / INSERT / ALTER / GRANT / REVOKE |
| Data isolation | DuckDB `_dataset_ownership` table; ChromaDB `user_id` metadata filter |
| Ownership checks | Every API endpoint verifies `user_id == current_user.id` |

## Future work

- Docker-compose for local dev
- OAuth via NextAuth (Google, GitHub)
- LangSmith integration for observability and tracing
- Anomaly / trend detection agent (5th specialist)
- Scheduled query reports + email delivery via AWS Lambda / EventBridge
- Live streaming of token output (current SSE streams step events, not tokens)
