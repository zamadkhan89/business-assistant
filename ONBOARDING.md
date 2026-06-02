# Business Assistant — Complete Onboarding & Feature Guide

> This file covers everything you need to understand the system, demo it, and extend it.
> **New here? Start at Section 0 — it tells you exactly which document to read first and why.**

---

## 0. Documentation Map — Where to Start

There are several documents in this project. Each has a different purpose. Here is the order to read them and what each one is for.

### Reading order for a new person

| Step | Document | Purpose | Time |
|---|---|---|---|
| 1 | **This file** (`ONBOARDING.md`) | Complete hands-on guide — what the system does, how every feature works, how to run it, how to inspect the data | 20 min read |
| 2 | [`README.md`](README.md) | Quick-reference summary — tech stack, setup commands, feature list, security controls | 5 min |
| 3 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Deep technical design — agent responsibilities, state flow, data layer, auth, design decisions with trade-offs | 15 min |
| 4 | [`docs/DEMO_SCRIPT.md`](docs/DEMO_SCRIPT.md) | Timed 8-minute demo script — exact steps to show the system to anyone, anticipated questions and answers | Before any demo |
| 5 | [`PROGRESS.md`](PROGRESS.md) | Full build log — every session, every decision, what was built on which day | For historical context |

### Other documents (situational)

| Document | Use it when… |
|---|---|
| [`MASTER_PROMPT.md`](MASTER_PROMPT.md) | You want to understand the original 14-day build plan, locked architectural decisions, and the "why" behind major choices |
| [`docs/SLIDES.md`](docs/SLIDES.md) | You are preparing a presentation or defense — contains 8 slides with speaker notes and timing |
| [`CLAUDE.md`](CLAUDE.md) | You are starting a Claude Code AI session — this is the machine-readable project brief that Claude reads first |

### What each document does NOT cover

- `ONBOARDING.md` does not explain how to run tests in detail → see `README.md`
- `README.md` does not explain the internal agent design → see `ARCHITECTURE.md`
- `ARCHITECTURE.md` does not contain demo steps → see `DEMO_SCRIPT.md`
- `PROGRESS.md` is a log, not a guide — do not start here

### One-sentence summary of the whole system

> Business Assistant takes a plain-English question, finds the right database tables using AI embeddings, generates SQL, optionally asks for your approval, executes the query on DuckDB or AWS Athena, and returns an interactive chart with a written summary — all in one conversation.

---

## 1. What This System Does (30-Second Pitch)

> "I built a multi-agent conversational analytics system that lets non-technical users
> query business data in plain English. Three things make it more than a chatbot wrapper:
> it uses embeddings to pick the right tables from a large schema, it learns your company's
> business definitions from a glossary you maintain, and it never runs a SQL query without
> your explicit approval — using LangGraph's interrupt-and-resume primitive to keep a human
> in the loop."

Post-defense additions: AWS Athena cloud integration, saved queries with inline re-execution, daily routines for recurring analysis batches, redesigned home page with live workspace stats, admin panel with per-user streaming and SQL approval toggles, SSE streaming responses, and full multi-user privacy isolation.

---

## 2. The Two Primary Databases — Know This Cold

**Rule: these two databases never store each other's data.** One handles operational/auth data, the other handles analytical queries.

### PostgreSQL — operational database

Everything about users, conversations, and configuration lives here.

| Table | What it stores |
|---|---|
| `users` | Accounts — email, password hash, admin/blocked status, streaming & SQL approval settings |
| `threads` | Conversation sessions (id, user_id, title, timestamps) |
| `messages` | Every message with metadata (chart JSON, executed SQL, agent steps) |
| `glossary_entries` | User-defined business term definitions |
| `saved_queries` | Bookmarked questions with stored SQL and results |
| `routines` | Named sets of recurring questions |
| `athena_configs` | AWS credentials per user; global config uses `user_id=NULL, is_global=TRUE` |
| `table_metadata` | Table descriptions, business context, display names, join hints |
| `column_metadata` | Column descriptions, KPI definitions, sample values |
| `admin_audit_log` | Every admin action with timestamp and actor |
| `email_verification_tokens` | Short-lived email verification codes |
| `password_reset_tokens` | Short-lived password reset tokens |

**Why PostgreSQL?** Relational, transactional, required by LangGraph's `AsyncPostgresSaver` checkpointer.

---

### DuckDB — analytical database

Only business/analytical data lives here. No user accounts, no auth, no conversation history.

| Table | What it stores |
|---|---|
| `customers` | Northwind sample customers (built-in seed data) |
| `products` | Northwind sample products (built-in seed data) |
| `orders` | Northwind sample orders (built-in seed data) |
| `order_items` | Northwind sample order line items (built-in seed data) |
| `u{prefix}_{name}` | User-uploaded CSV tables — e.g. `u6c06a166_car_prices` |
| `_dataset_ownership` | Tracks which `user_id` owns each uploaded table (data isolation) |
| `_athena_direct_refs` | Tables registered for direct Athena query (schema only, no data) |
| `_dataset_athena_meta` | Metadata for Athena-ingested tables |

**Why DuckDB?** In-process, columnar, fast for analytical queries, SQL-compatible with AWS Athena.

DuckDB is a single file at `backend/business_assistant.db` — no server process needed.

> **Note on `_dataset_ownership`:** This is a DuckDB tracking table — it stores `user_id` strings to enforce data isolation. It is NOT the same as the `users` table in PostgreSQL. It only stores the UUID string, not any user details.

---

## 3. The Four Agents — Roles and Responsibilities

```
User message
     │
     ▼
┌─────────────┐
│  Supervisor │  Keyword-based intent: data_query / direct reply
│             │  Fast, deterministic — no LLM call
└──────┬──────┘
       │ (data_query only)
       ▼
┌─────────────┐
│Schema Agent │  ChromaDB semantic search → finds relevant tables (user-scoped)
│             │  Injects glossary terms + preloaded table metadata
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  SQL Agent  │  Generates SQL (LLM, temp=0) → validates → explains
│             │  Athena direct mode: generates Presto-compatible SQL
│             │  ──── interrupt() ────  HITL approval panel shown to user
│             │  On resume: approve / reject / edit → sets current_step
└──────┬──────┘
       │ (approved only)
       ▼
┌─────────────┐
│Analysis     │  Routes by query_engine: DuckDB (default) or Athena direct
│  Agent      │  DataFrame → pick_chart_type → Plotly JSON → rich LLM summary
└─────────────┘
```

### Agent files
| Agent | File | Key responsibility |
|---|---|---|
| Supervisor | [backend/app/agents/supervisor.py](backend/app/agents/supervisor.py) | Intent classification |
| Schema | [backend/app/agents/schema_agent.py](backend/app/agents/schema_agent.py) | Table linking via ChromaDB (user-scoped) |
| SQL | [backend/app/agents/sql_agent.py](backend/app/agents/sql_agent.py) | SQL generation, validation, HITL interrupt |
| Analysis | [backend/app/agents/analysis_agent.py](backend/app/agents/analysis_agent.py) | Execution (DuckDB or Athena), charting, rich summarisation |
| Graph wiring | [backend/app/agents/graph.py](backend/app/agents/graph.py) | StateGraph, edges, checkpointer |
| Shared state | [backend/app/agents/state.py](backend/app/agents/state.py) | TypedDict passed between all nodes |

---

## 4. Memory: Short-Term vs Long-Term

### Short-term memory (within a single graph run)

`AgentState` is the TypedDict that flows through every node. It is LangGraph's working memory — carrying the user's message, schema found, SQL generated, results produced, and more. Each node reads from it and writes updates back.

Key fields added post-defense:
- `user_id` — passed through to schema agent for data isolation
- `query_engine` — `"duckdb"` or `"athena_direct"` (set by chat.py based on selected datasets)
- `athena_creds` — pre-loaded from Postgres before `ainvoke()` (Windows asyncio safety)
- `preloaded_metadata` — pre-loaded table descriptions and KPIs (same reason)
- `selected_datasets` — explicit dataset filter; empty means all user tables
- `sql_approval_required` — pre-loaded from `current_user.sql_approval_required`; when false, sql_agent skips `interrupt()` and executes immediately

### Long-term memory (across requests and server restarts)

LangGraph's checkpointer serialises the entire `AgentState` to storage after every node completes.

| Environment | Checkpointer | Persistence |
|---|---|---|
| Windows dev | `MemorySaver` | In-process; lost on server restart |
| Linux / production | `AsyncPostgresSaver` | Stored in PostgreSQL; survives restarts |

**Why does Windows use MemorySaver?** uvicorn on Windows uses the ProactorEventLoop by default, which is incompatible with psycopg3 async connections. The code in `main.py` detects this and falls back automatically. Chat messages are *still* written to PostgreSQL (via SQLAlchemy + asyncpg, which works fine) so the history sidebar works.

---

## 5. Human-in-the-Loop (HITL) — The Demo Centrepiece

### What happens step by step

HITL is **opt-in per user** — the admin enables it via the Admin Panel toggle. When disabled (default), SQL executes immediately without pausing.

```
POST /chat { thread_id, message }
  │
  ├─ graph.ainvoke() runs supervisor → schema → sql_agent
  │
  ├─ If sql_approval_required = false (default):
  │    sql_agent returns draft_sql immediately → analysis_agent executes
  │
  ├─ If sql_approval_required = true:
  │    sql_agent calls interrupt({"draft_sql": ..., "sql_explanation": ...})
  │    LangGraph STOPS execution here. Checkpoints state to storage.
  │    ainvoke() returns immediately with __interrupt__ in the result.
  │    chat.py detects __interrupt__, returns:
  │      { status: "needs_approval", draft_sql, sql_explanation }
  │    Frontend shows amber approval panel with SQL + explanation
  │
  └─ User clicks Approve / Edit / Reject (only when approval is required)

User clicks Approve / Edit / Reject
  │
POST /chat/resume { thread_id, action: "approve" }
  │
  ├─ graph.ainvoke(Command(resume={action: "approve"}), config)
  │    LangGraph RELOADS checkpoint for thread_id.
  │    sql_agent sets current_step = "approved".
  │    analysis_agent executes SQL, builds chart, summarises.
  │
  └─ Returns { status: "done", content, chart_json, query_results }
```

### Code locations
- `interrupt()` call: [backend/app/agents/sql_agent.py](backend/app/agents/sql_agent.py)
- Resume endpoint: [backend/app/api/chat.py](backend/app/api/chat.py)
- Frontend panel: [frontend/app/chat/page.tsx](frontend/app/chat/page.tsx)

---

## 6. Schema Linking with ChromaDB

### How it works

1. At server startup, `init_chroma()` embeds every table's name + column list into a ChromaDB collection.
2. When a question arrives, `search_schema(query, user_id)` queries ChromaDB filtered by `user_id` and returns the top-K most semantically similar tables.
3. Only those tables' full schemas (column names, types, 2 sample rows, plus any metadata enrichment) are sent to the SQL agent's LLM prompt.

### Multi-user isolation

`describe_user_tables(user_id)` returns built-in tables + only the tables that specific user uploaded or ingested. Even if ChromaDB returns a table name, it is filtered through this list before being sent to the LLM.

ChromaDB is also queried with `where={"user_id": user_id}` metadata filter so semantic search itself is scoped per user.

---

## 7. Business Glossary

### How it flows

1. User adds a glossary entry via the `/glossary` page.
2. Entry is stored in PostgreSQL `glossary_entries` table.
3. On every `POST /chat`, the chat endpoint loads all of the user's glossary entries and puts them in `AgentState.glossary_context`.
4. The schema agent appends a "Business glossary" section to its reply message.
5. The SQL agent injects the definitions directly into the LLM prompt before generating SQL.

### Visibility in chat

The chat page shows a **green banner** when glossary terms are active:
> "3 glossary terms active — business definitions are applied to every query automatically."

The sidebar navigation also shows a badge with the term count. This ensures users know their definitions are being used.

---

## 8. CSV Upload Flow

```
User selects file in frontend
  │
POST /api/datasets/upload (multipart, 10 MB limit, .csv only)
  │
  ├─ ingest_csv() reads bytes → pd.read_csv → registers as DuckDB temp view
  ├─ _next_versioned_name(base, user_id, conn) checks existing tables:
  │    • if "sales" not owned by user → use "sales"
  │    • if "sales" already exists → use "sales_v2"
  │    • if "sales_v2" exists → use "sales_v3" (up to _v98)
  ├─ CREATE TABLE u{user_prefix}_{versioned_name}  (never CREATE OR REPLACE)
  ├─ Writes ownership record to _dataset_ownership in DuckDB
  │
  └─ refresh_chroma() re-embeds all tables including the new one
       → new table is now discoverable by semantic search
```

**Important:** Uploading the same filename twice creates `sales_v2` instead of overwriting `sales`. User data is never silently lost.

---

## 9. AWS Athena Integration

The Athena page (`/athena`) lets users connect an AWS Athena workspace. There are two modes:

### Ingest mode
- Choose a table from Athena's `information_schema`
- The system queries Athena for the data and loads it into DuckDB
- From that point, queries run at DuckDB speed, no AWS costs per query

### Direct mode
- Register the table name in DuckDB's `_athena_direct_refs` view (schema only, no data copied)
- Queries against this table are routed to Athena via boto3 at execution time
- Better for very large tables where copying data locally is impractical

### Credentials
- **Per-user**: stored in the `AthenaConfig` PostgreSQL table with the user's ID
- **Global**: an admin (see `ADMIN_EMAILS` env var) can set global credentials stored with `user_id = "__global__"` — all users without personal credentials inherit these
- Personal credentials take priority over global

### Windows asyncio note
Athena credentials and table metadata are **pre-loaded** in the FastAPI endpoint before calling `graph.ainvoke()`. This avoids calling `asyncio.run()` inside a thread pool which crashes on Windows' ProactorEventLoop. The same pattern is used in the routines run endpoint.

---

## 10. Saved Queries

Users can save any successful query (name + question + SQL + results) via the bookmark button in chat.

The `/saved-queries` page shows all saved queries. Clicking **Run** re-executes the stored SQL against the current data and shows results inline:
- A fresh interactive chart via ChartMessage
- A results table labelled "fresh" (re-run) or "saved" (original)
- The button cycles: **Run** → **Running…** → **Re-run**

No redirect to chat — everything stays on the page.

---

## 11. Daily Routines

The `/routines` page lets users define named sets of recurring questions.

- **Create** a routine with a name and N questions
- **Run** — all questions execute sequentially through the full LangGraph pipeline (Supervisor → Schema → SQL → Analysis), each with a fresh thread ID
- Results appear per-question: chart, data table, executed SQL, and any error

This replaces the need to manually re-ask the same set of questions every morning.

---

## 12. Authentication Flow

```
Signup (POST /auth/signup)
  → bcrypt(password, rounds=12) → store User in PostgreSQL
  → return JWT (HS256, 24h, signed with SECRET_KEY)
  → isAdmin = email in ADMIN_EMAILS env var

Login (POST /auth/login)
  → verify bcrypt hash → issue JWT

Frontend (NextAuth credentials provider)
  → calls POST /auth/login → stores JWT + isAdmin in session cookie
  → every subsequent API call adds: Authorization: Bearer <token>

Protected endpoint (Depends(get_current_user))
  → verifies JWT signature + expiry
  → returns User object, or 401 if invalid
```

---

## 13. The LLM Layer

All LLM calls go through `get_llm(temperature)` in [backend/app/core/llm.py](backend/app/core/llm.py).

**Currently configured:** Anthropic Claude (`claude-sonnet-4-6`) via `LLM_PROVIDER=anthropic`.

| Temperature | Used for | Why |
|---|---|---|
| 0.0 | SQL generation, intent classification | Deterministic — same question, same SQL |
| 0.3 | Result summarisation, SQL explanation | Slight creativity for natural-sounding output |

Rich summary format (`summarize_result`):
- Up to 30 preview rows + computed stats (min/max/avg/total per numeric column)
- Structured Markdown: **Key finding**, Notable patterns, Highlights with specific numbers
- Falls back to a simple row-count message if the LLM call fails

---

## 14. Running the System Locally

### Option A — One command (recommended)

```powershell
.\dev.ps1          # start backend + frontend in separate windows
.\dev.ps1 status   # check both are running + health check
.\dev.ps1 stop     # stop both when done
```

| Window says | Means |
|---|---|
| `INFO: Application startup complete.` | Backend is ready |
| `Local: http://localhost:3001` | Frontend is ready |

### Option B — Manual (two terminals)

**Terminal 1 — Backend**
```powershell
cd d:\business-assistant\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend**
```powershell
cd d:\business-assistant\frontend
npm run dev
```

### Required environment variables

All in `backend/.env`:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/business_assistant
POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/business_assistant
SECRET_KEY=<any long random string>
ANTHROPIC_API_KEY=<your key>
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ADMIN_EMAILS=your@email.com   # optional, for global Athena config
```

### Verify tests

```powershell
cd d:\business-assistant\backend
.venv\Scripts\Activate.ps1
python -m pytest          # all tests must pass
```

---

## 15. Inspecting the Databases (for demos and debugging)

The system uses two databases for different purposes. Here is how to open and browse each one.

---

### PostgreSQL — users, conversations, glossary, saved queries, routines, admin data

**Tool: pgAdmin 4** — installed automatically with PostgreSQL on Windows.

1. Open **pgAdmin 4** from the Start menu
2. Connect to server: host `localhost`, port `5432`, username `postgres`, password `postgres`
3. Navigate: `Servers → PostgreSQL 16 → Databases → business_assistant → Schemas → public → Tables`
4. Right-click any table → **View/Edit Data → All Rows**

**Key tables to show a supervisor:**

| Table | What it contains |
|---|---|
| `users` | All registered accounts, email, admin/blocked status, streaming/approval settings, storage quota |
| `threads` | Every conversation (id, user_id, title, timestamps) |
| `messages` | Every message sent and received, with metadata (chart JSON, SQL, agent steps) |
| `glossary_entries` | User-defined business terms and their definitions |
| `saved_queries` | Bookmarked questions with stored SQL and results |
| `routines` | Named sets of recurring questions |
| `admin_audit_log` | Every admin action (block, delete, settings change) with timestamp and actor |
| `athena_configs` | AWS Athena credentials per user (and global `__global__` entry) |
| `table_metadata` | Table and column descriptions, KPI definitions, join hints added via Catalog |

---

### DuckDB — analytical data (CSV uploads, Northwind sample, Athena ingested tables)

DuckDB is a single file at `backend/business_assistant.db`. There is no server — it is embedded in the Python process.

**Tool: DBeaver Community** (free, supports DuckDB natively)

1. Download from **dbeaver.io** → install
2. File → New Database Connection → search **DuckDB** → Next
3. Database: browse to `d:\business-assistant\backend\business_assistant.db`
4. Click **Finish** → expand the connection to browse tables

**Key tables/views in DuckDB:**

| Table | What it contains |
|---|---|
| `customers` | Northwind sample customers (built-in) |
| `products` | Northwind sample products (built-in) |
| `orders` | Northwind sample orders (built-in) |
| `order_items` | Northwind sample order line items (built-in) |
| `_dataset_ownership` | Maps every uploaded table to its owning `user_id` |
| `u{prefix}_{name}` | User-uploaded CSV tables (e.g. `u3a2b_sales_data`) |
| `_athena_direct_refs` | Tables registered for direct Athena query (schema only, no data) |

> **Note:** DuckDB is an in-process database — it is only accessible when the backend is NOT running (both processes cannot open the same file simultaneously on Windows). Stop the backend first before opening it in DBeaver.

---

### Built-in Admin Panel — quickest option, no extra tools needed

If the backend and frontend are running, open **http://localhost:3001/admin** (admin account required).

The admin panel shows in a clean UI:
- All registered users with their dataset count, thread count, and storage used
- Per-user storage bar and quota setting
- User datasets (table names + row counts)
- User conversations (titles + timestamps)
- Feature toggles: Streaming enabled / SQL Approval required
- Full admin audit log with timestamps

This is the cleanest thing to show a supervisor — it runs directly in the browser with no extra tools.

---

### FastAPI Swagger UI — inspect and test every API endpoint

With the backend running, open **http://localhost:8000/docs**

- Lists every API endpoint with its request/response schema
- You can run live requests directly from the browser (click an endpoint → Try it out → Execute)
- Useful for showing how data flows through the system at the API level
- Requires a JWT token for protected endpoints: log in first via `/auth/login`, copy the `access_token`, then click **Authorize** at the top and paste it

---

## 16. Known Limitations — and Why They Exist

| Limitation | Why it exists | What you would do with more time |
|---|---|---|
| MemorySaver on Windows dev | ProactorEventLoop / psycopg3 incompatibility | Run on Linux or Docker |
| No live cloud deploy | Time constraint; local demo is the fallback | Railway + Vercel config files are ready (Procfile, runtime.txt) |
| ChromaDB rebuilt on restart | EphemeralClient; no persistence | Switch to ChromaDB's DiskClient or pgvector |
| Athena direct: no HITL edit | Presto SQL differs from DuckDB SQL; users can't easily edit it | Add Athena-aware validation in the approval panel |
| Settings changes require page reload | `streaming_enabled` is fetched on mount, not subscribed live | Add a WebSocket or polling refresh |

---

## 17. File Map — Where Is Everything

> For a higher-level explanation of the system design, read [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

```
backend/
  app/
    agents/
      state.py          ← shared AgentState TypedDict (includes athena_creds, preloaded_metadata)
      supervisor.py     ← intent classifier (keyword-based, fast)
      schema_agent.py   ← ChromaDB table linking (user-scoped)
      sql_agent.py      ← SQL gen + validation + interrupt()
      analysis_agent.py ← DuckDB/Athena execution + charting + rich summary
      graph.py          ← StateGraph wiring
    api/
      auth.py           ← signup / login / me (isAdmin in response)
      chat.py           ← POST /chat and POST /chat/resume (pre-loads creds + metadata)
      datasets.py       ← CSV upload (versioned) / list / export
      glossary.py       ← glossary CRUD
      threads.py        ← thread list + message history
      saved_queries.py  ← save / list / delete / run inline
      routines.py       ← routine CRUD + run all questions
      athena.py         ← Athena config + table management (ingest + direct modes)
      catalog.py        ← table + column metadata (descriptions, KPIs, join hints) — routes at /api/catalog/*
    core/
      config.py         ← all env vars (incl. ADMIN_EMAILS, QUERY_TIMEOUT_SECONDS)
      security.py       ← JWT + bcrypt
      llm.py            ← single LLM entrypoint
      db.py             ← SQLAlchemy async engine
    data/
      duckdb_connector.py ← DuckDB I/O, _next_versioned_name, _dataset_ownership
      sample_data.py    ← Northwind-inspired seed data
    models/             ← SQLAlchemy ORM models
      user.py, thread.py, message.py
      glossary.py, saved_query.py
      routine.py        ← Routine model (name, questions JSON, user_id)
      athena_config.py  ← AthenaConfig model (creds, workgroup, output bucket)
      table_metadata.py ← TableMetadata + ColumnMetadata models
  tests/
    accuracy/           ← 20-question eval harness

frontend/
  app/
    home/               ← redesigned landing page with stat cards + explainer
    (auth)/login/       ← login page
    (auth)/signup/      ← signup page
    chat/               ← main chat UI (glossary badge + banner, Athena warning)
    glossary/           ← glossary CRUD page
    saved-queries/      ← inline query runner (run / re-run, chart + table)
    routines/           ← daily routine manager (create, run all, per-question results)
    athena/             ← Athena data source manager (config, ingest, direct)
  components/
    chat/               ← MessageBubble, CodeBlock, ChartMessage
    ThemeProvider.tsx   ← dark/light mode
    ThemeToggle.tsx
  lib/
    auth.ts             ← NextAuth config (accessToken + isAdmin + streamingEnabled + sqlApprovalRequired in session)

docs/
  ARCHITECTURE.md       ← system design document
  DEMO_SCRIPT.md        ← timed demo with Q&A
  SLIDES.md             ← defense slides with speaking notes
```

---

*Updated 2026-06-02. Reflects all post-defense features including per-user streaming/approval toggles, admin panel improvements, and Business Assistant rebranding.*
