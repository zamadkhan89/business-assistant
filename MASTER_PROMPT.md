# MASTER_PROMPT.md

> **For Claude Code**: This file is the source of truth for this project. Read it at the start of every session before doing anything else. If anything in the user's request contradicts this file, ask before proceeding. If you propose changes to the plan, write them into this file so future sessions stay aligned.

---

## How to use this file

**User**: At the start of each session in Claude Code, say one of:
- "Read MASTER_PROMPT.md, then tell me what we should do today" — when you want guidance
- "Read MASTER_PROMPT.md, we're on Day N, continue" — when you know where you are
- "Read MASTER_PROMPT.md and PROGRESS.md, what's next?" — once PROGRESS.md exists

**Claude Code**: Always read this file first. Then read `PROGRESS.md` (which you maintain) to know what's done. Then propose the next concrete step. Never start coding until the user confirms the step.

---

## Part 1 — Project Identity

### What this is
A **multi-agent business assistant** that lets non-technical users query data using natural language, with three production-grade differentiators that make it more than an LLM wrapper:

1. **Schema linking with embeddings** — Picks the right tables/columns from a database with many tables, instead of dumping the whole schema into the prompt.
2. **Business glossary** — User-editable definitions ("revenue means net of returns") stored persistently and retrieved automatically when relevant.
3. **Human-in-the-loop SQL approval** — User reviews/edits/rejects generated SQL before it executes, using LangGraph's `interrupt()` primitive.

### Who this is for
A **solo BS-IT final year project**, defended in 14 days. Author is comfortable in Python, has limited JavaScript experience, has Claude Pro and an Anthropic API key.

### What this is NOT
- Not an enterprise product
- Not a multi-tenant SaaS
- Not a research paper
- Not a place to learn 5 new technologies — only learn what's necessary

### Defense narrative (memorize this)
> "I built a multi-agent system using LangGraph that solves three real problems with conversational analytics: it picks the right tables from a large schema using embeddings, it captures business-specific definitions in a glossary, and it asks the user to approve every SQL query before running it. The architecture separates concerns across a Supervisor and three specialist agents — Schema, SQL, and Analysis — and uses LangGraph's interrupt-and-resume to keep humans in the loop."

---

## Part 2 — Locked Architectural Decisions

These are decided. Do not propose changes unless the user explicitly asks.

| Decision | Choice | Why |
|---|---|---|
| Agent framework | LangGraph | First-class checkpointing, interrupt(), subgraphs |
| Agent count | 1 supervisor + 3 specialists (Schema, SQL, Analysis) | Sweet spot for scope; more agents = more debugging |
| Agent pattern | Supervisor-with-specialists, sub-agents exposed as tools | LangChain's recommended pattern |
| Backend | FastAPI (Python 3.11+), async | Type-safe, fast, hosts SSE cleanly |
| Frontend | Next.js 14 App Router, TypeScript, Tailwind, shadcn/ui | Production-grade chat UX, NextAuth for auth |
| Frontend bootstrap | Vercel AI Chatbot starter template | Saves 2 days of frontend work |
| Auth | FastAPI issues JWT, NextAuth credentials provider validates same JWT | Standard pattern, both sides verify with shared secret |
| Database | PostgreSQL (single DB for users, chats, glossary, LangGraph checkpointer) | Required for PostgresSaver |
| Data layer | DuckDB (in-process) for analytical data + CSV uploads | SQL dialect compatible with Athena for future migration |
| Vector store | ChromaDB (local) for schema embeddings | Lightweight, no separate service |
| LLM access | LangChain's `init_chat_model()` abstraction, env-var driven | Lets user swap Anthropic/OpenAI/Google with one variable change |
| Primary LLM | Anthropic Claude (claude-opus-4-5 default) | Best at SQL gen, strongest reasoning |
| Visualization | Plotly via react-plotly.js | Interactive, good chart variety, renders cleanly in React |
| Streaming | Server-Sent Events from FastAPI to Next.js | Standard, no WebSocket complexity |
| Dev environment | Local Python venv, local Postgres, no Docker until post-defense | Fewer moving parts during build |
| OS target | Windows 11, PowerShell commands | Author's machine |

### Anti-patterns — do not do these
- ❌ Don't propose Streamlit (we evaluated and rejected it for HITL/auth reasons)
- ❌ Don't propose AWS Athena before defense (post-defense work)
- ❌ Don't propose Docker before defense (post-defense work)
- ❌ Don't propose more agents than the four specified
- ❌ Don't propose multiple databases for different data types — one Postgres only
- ❌ Don't write 200+ lines of frontend by hand — use the starter template, modify it
- ❌ Don't skip writing tests — every endpoint and every agent gets at least one test
- ❌ Don't skip the buffer days (Day 7, Day 14)

---

## Part 3 — The 14-Day Plan

Each day produces a **demoable, testable deliverable**. End-of-day means: code runs, tests pass, you can show the new feature working end-to-end before stopping.

### Day 1 — Repo + FastAPI auth foundation
**Goal**: I can run the backend, sign up, log in, and hit a protected endpoint.

Build:
- Repo structure: `backend/`, `frontend/` (placeholder), `docs/`, `.gitignore`, `README.md`
- Python venv at `backend/.venv`
- `requirements.txt` covering all 14 days (FastAPI, uvicorn, langgraph, langchain, langchain-anthropic, langchain-openai, langchain-google-genai, anthropic, openai, google-generativeai, asyncpg, sqlalchemy[asyncio], alembic, pydantic, pydantic-settings, python-jose[cryptography], passlib[bcrypt], chromadb, duckdb, plotly, pandas, pytest, pytest-asyncio, httpx)
- Postgres database `business_assistant`
- Alembic migrations for: `users`, `threads`, `messages`, `glossary_entries`, `saved_queries` — all with UUID primary keys, `created_at`, `updated_at`
- `app/core/config.py` — Pydantic settings reading `.env`
- `app/core/security.py` — JWT issue/verify, bcrypt password hashing
- `app/core/llm.py` — wraps `init_chat_model()`, swaps provider via `LLM_PROVIDER` env var (anthropic/openai/google)
- `app/api/auth.py` — `POST /auth/signup`, `POST /auth/login`, `GET /auth/me`
- `app/main.py` — FastAPI app, includes auth router, health check
- `tests/test_auth.py` — passing tests for all four auth endpoints
- `.env.example` documenting every required variable
- `CLAUDE.md` summarizing decisions (separate from this file — short, project-specific)

**End of day**: `pytest` passes. `curl POST /auth/signup`, `POST /auth/login`, `GET /auth/me` all work.

### Day 2 — Next.js frontend with auth
**Goal**: I can sign up and log in via a real web UI.

Build:
- Bootstrap Next.js from Vercel AI Chatbot starter (`npx create-next-app` with the template)
- Strip out OpenAI-specific code; we're calling our own backend
- NextAuth credentials provider that POSTs to `backend/auth/login`, stores JWT in session
- `/signup` and `/login` pages styled with shadcn/ui
- `/chat` route protected — redirects to `/login` if no session
- Placeholder chat UI on `/chat` that just echoes input via a `POST /api/chat/echo` backend endpoint, to prove the auth-protected request flow works

**End of day**: I can sign up in the browser, log in, get redirected to `/chat`, type a message, see it echoed back. Logging out and refreshing kicks me to `/login`.

### Day 3 — LangGraph supervisor + checkpointer
**Goal**: A real LangGraph supervisor agent runs through Postgres-checkpointed state.

Build:
- `app/agents/state.py` — TypedDict for the shared state (messages, current_step, schema_context, draft_sql, query_results, etc.)
- `app/agents/supervisor.py` — minimal supervisor that classifies user intent and routes (only routes to "echo" placeholder for now)
- `app/agents/graph.py` — builds the StateGraph, attaches PostgresSaver checkpointer
- `POST /api/chat` endpoint that takes `{thread_id, message}`, runs the graph, returns the final state
- Thread management: thread_id stored in `threads` table, messages stored in `messages` table after each graph run
- Test: send two messages on the same thread, verify the second sees the first via checkpointer

**End of day**: Frontend chat sends real messages to a real LangGraph supervisor, conversation history persists across page refreshes.

### Day 4 — Schema Agent
**Goal**: System knows what tables exist and which are relevant to a question.

Build:
- `app/data/duckdb_connector.py` — wraps DuckDB; introspects tables, columns, types, sample rows
- `app/data/sample_data.py` — loads a built-in sample dataset (e.g., Northwind subset or e-commerce CSV) into DuckDB on startup
- `app/agents/schema_agent.py` — LangGraph subgraph
  - On startup: embeds table+column descriptions into ChromaDB
  - Tool `search_schema(query)` — semantic search returning top-K relevant tables
  - Tool `get_glossary(term)` — looks up business glossary entries from Postgres
  - Returns a "context bundle" written to graph state
- Wire Schema Agent into the supervisor's routing
- Test: ask "show me top customers", verify schema_context populated with `customers`, `orders` tables

**End of day**: Frontend chat — when you ask a data question — shows relevant tables identified, even though no SQL runs yet.

### Day 5 — SQL Agent
**Goal**: System generates valid SQL from natural language + schema context.

Build:
- `app/agents/sql_agent.py` — LangGraph subgraph
  - Takes user question + schema_context from state
  - Tool `generate_sql(question, schema)` — LLM call, returns SQL
  - Tool `validate_sql(sql)` — parses with sqlparse, blocks DROP/DELETE/UPDATE/TRUNCATE/INSERT/ALTER
  - Tool `explain_sql(sql)` — generates a plain-English explanation of what the SQL does
  - Writes `draft_sql` and `sql_explanation` to state
- Wire SQL Agent after Schema Agent in supervisor
- Test: ask "show me top 5 products by sales", verify draft_sql contains a valid SELECT

**End of day**: Asking a data question shows generated SQL + explanation in the chat. SQL has not run yet — that's Day 6.

### Day 6 — Human-in-the-Loop approval
**Goal**: User sees generated SQL, approves/edits/rejects before execution.

This is the hardest day. Budget for it.

Build:
- Add `interrupt()` call in SQL Agent right after validation, before any execution path
- `app/agents/graph.py` updated — when graph hits the interrupt, the API returns a `needs_approval` event with the draft SQL
- FastAPI SSE endpoint `GET /api/chat/stream` — streams events as the graph runs (regular tokens + special `needs_approval` event)
- FastAPI endpoint `POST /api/chat/resume` — accepts `{thread_id, decision: 'approve'|'reject'|'edit', edited_sql?}`, resumes the graph with `Command(resume=...)`
- Frontend: SSE consumer that pauses the chat UI when `needs_approval` arrives, shows a modal with the SQL, three buttons (Approve/Edit/Reject), POSTs the decision to resume
- Test: end-to-end flow — ask question → see SQL in modal → click Approve → graph resumes → see "(approved, would run now)" in chat

**End of day**: HITL works. SQL still doesn't actually execute against DuckDB — that's Day 8 (Day 7 is buffer).

### Day 7 — Buffer day
**Goal**: Catch up on whatever broke. End-to-end smoke test.

If everything is on schedule:
- Polish the SQL approval modal UI
- Add syntax highlighting to the SQL display (Prism.js or react-syntax-highlighter)
- Improve error handling — what if the LLM returns invalid SQL? What if validation fails?
- Add logging throughout

If you're behind:
- Don't add anything new. Just fix what's broken from Days 1-6.

**End of day**: Days 1-6 work flawlessly. You are confident moving forward.

### Day 8 — Analysis Agent
**Goal**: Approved SQL runs, results return as a chart.

Build:
- `app/agents/analysis_agent.py` — LangGraph subgraph
  - Tool `execute_sql(sql)` — runs against DuckDB, returns DataFrame as records
  - Tool `pick_chart_type(df)` — heuristic based on column types and row count (1 numeric column + 1 categorical = bar; 2 numeric = scatter; time series = line; etc.)
  - Tool `build_plotly_figure(df, chart_type)` — returns Plotly figure JSON
  - Tool `summarize_result(df)` — 1-2 sentence summary via LLM
- Wire Analysis Agent after SQL Agent (post-approval)
- Frontend: render Plotly figure JSON via react-plotly.js in the chat message

**End of day**: Full flow works — ask question, see schema, see SQL, approve, see chart and summary.

### Day 9 — CSV upload + export
**Goal**: User can upload a CSV and ask questions about it.

Build:
- `POST /api/datasets/upload` — accepts multipart CSV, stores it, ingests into DuckDB as a new table named after the file (sanitized)
- After ingest: re-embed the schema in ChromaDB so the new table is discoverable
- Frontend: file upload button in chat sidebar, shows uploaded datasets list
- `GET /api/datasets/:id/export` — runs a saved query, returns CSV download
- Frontend: "Download as CSV" button on any chart message

**End of day**: I can upload `sales_data.csv`, ask questions about it, and download results.

### Day 10 — Glossary CRUD + chat history sidebar
**Goal**: User can manage business glossary entries and review past chats.

Build:
- `app/api/glossary.py` — CRUD endpoints for `/api/glossary` (list, create, update, delete)
- Frontend `/glossary` page — table view with add/edit/delete
- Verify Schema Agent's `get_glossary()` retrieves these entries during a query
- Chat history sidebar on `/chat` — lists user's threads, click to load
- `GET /api/threads` and `GET /api/threads/:id/messages` endpoints

**End of day**: I can add a glossary entry like "revenue: gross_amount minus returned_amount", ask a question using "revenue", and see the agent use that definition.

### Day 11 — Accuracy testing + iteration
**Goal**: Measured baseline accuracy on a real-shaped dataset.

Build:
- `tests/accuracy/` — fixture file with 20 question/expected-answer pairs against the sample dataset
- `tests/accuracy/run_eval.py` — runs each question through the graph, compares output, reports pass rate
- Run it. Identify top 3 failure modes. Fix them.
- Common fixes: tighten Schema Agent prompt with examples, add few-shot examples to SQL Agent, improve glossary lookup precision

**End of day**: Documented accuracy number (e.g., "17/20 correct, 85%"), with notes on the failures.

### Day 12 — UI polish + deploy
**Goal**: Production-feeling demo, deployed to a public URL.

Build:
- Loading states on every async action (chat send, file upload, glossary save)
- Error states (network errors, API errors, validation errors) with friendly messages
- Empty states (no chats yet, no glossary yet, no datasets yet)
- Dark mode toggle
- Deploy frontend to Vercel
- Deploy backend to Railway or Render with managed Postgres
- Verify the deployed version works end-to-end

**End of day**: A public URL you can send to anyone and they can sign up, ask a question, see a chart.

### Day 13 — Documentation + report draft
**Goal**: Defense materials ready.

Build:
- `README.md` — what it is, screenshots, architecture diagram, how to run locally, tech stack, future work
- `docs/ARCHITECTURE.md` — the multi-agent design, why each agent exists, how state flows
- `docs/DEMO_SCRIPT.md` — what to demo at defense, in what order, with expected user questions
- Record demo video (5-7 minutes) — screen capture of the full flow
- FYP report draft — usually a separate document required by your university; lift sections from the proposal and add what you actually built

**End of day**: Everything written down, video recorded, ready to defend.

### Day 14 — Defense prep + final buffer
**Goal**: Walk into the defense calm.

Do:
- Practice the demo 3 times. Time yourself. Aim for 8 minutes.
- Build slides (8-10 slides max — problem, solution, architecture, three differentiators, demo, results, future work, questions)
- Anticipate questions: "Why these three agents?" "How does HITL work?" "Why DuckDB not Postgres for data?" "Why not just use ChatGPT?" Have a 30-second answer ready for each.
- If anything is broken from Day 12 deploy: fix it. The local demo is your fallback.

**End of day**: You are ready.

---

## Part 4 — Cut List (When You Fall Behind)

You will fall behind somewhere. When that happens, drop in this order. **Do not drop anything labeled non-negotiable.**

1. Drop dark mode (Day 12)
2. Drop deployed cloud version, demo locally (Day 12)
3. Drop chat history sidebar UI, query DB directly to demo (Day 10)
4. Drop glossary CRUD UI, manage via SQL inserts (Day 10)
5. Drop CSV export (keep upload) (Day 9)
6. Drop chart type heuristic, always use bar chart (Day 8)
7. Drop SQL edit-and-resubmit, only allow approve/reject (Day 6)
8. Drop token streaming, return full response at end (Day 6/10)

**Non-negotiables — never drop these**:
- Authentication (signup, login, session)
- Supervisor + Schema + SQL + Analysis agents (all four)
- Human-in-the-loop SQL approval (the demo centerpiece)
- At least one chart type displaying real query results
- Persistent chat history in Postgres
- Business glossary backend (UI optional)

---

## Part 5 — Conventions for Claude Code

### File organization
```
backend/
  app/
    main.py                  # FastAPI entry
    core/
      config.py              # Pydantic settings
      security.py            # JWT, hashing
      llm.py                 # init_chat_model wrapper
      db.py                  # SQLAlchemy session
    api/                     # FastAPI routers
      auth.py
      chat.py
      datasets.py
      glossary.py
    agents/                  # LangGraph
      state.py
      supervisor.py
      schema_agent.py
      sql_agent.py
      analysis_agent.py
      graph.py               # builds the StateGraph
    data/
      duckdb_connector.py
      sample_data.py
    models/                  # SQLAlchemy models
      user.py
      thread.py
      message.py
      glossary.py
  alembic/
  tests/
  .env.example
  requirements.txt
frontend/
  app/                       # Next.js App Router
    (auth)/login/page.tsx
    (auth)/signup/page.tsx
    chat/page.tsx
    glossary/page.tsx
  components/
    chat/
    ui/                      # shadcn components
  lib/
    auth.ts                  # NextAuth config
    api.ts                   # backend API client
docs/
PROGRESS.md                  # maintained by Claude Code, see below
MASTER_PROMPT.md             # this file
README.md
```

### Commit conventions
- Small commits, one logical change each
- Conventional commit prefix: `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
- Always commit after each completed task within a day; don't wait until end of day

### Testing rules
- Every API endpoint has at least one test
- Every agent has at least one isolated test
- Don't move to the next day if tests fail
- Use `pytest-asyncio` for async tests, `httpx.AsyncClient` for endpoint tests

### LLM call rules
- All LLM calls go through `app/core/llm.py` — never import Anthropic/OpenAI/Google SDK directly elsewhere
- Always log: model name, input tokens (estimate), output tokens (from response)
- Use temperature 0 for SQL generation, validation, schema linking; temperature 0.3-0.7 for summaries

### Error handling rules
- Tools return structured errors, not exceptions, so the agent can react
- API endpoints return proper HTTP status codes (400 for client errors, 500 for server)
- Never expose stack traces to the frontend in production mode

### Security rules
- Passwords: bcrypt, cost factor 12
- JWTs: HS256, 24-hour expiry, secret from env
- SQL validation: hard reject on DROP/DELETE/UPDATE/TRUNCATE/INSERT/ALTER/GRANT/REVOKE
- Never log secrets, JWTs, or full prompts containing user data
- All user-facing inputs validated via Pydantic models

---

## Part 6 — PROGRESS.md (Claude Code Maintains This)

Claude Code: at the end of every session, append to `PROGRESS.md` in this format:

```
## Day N — YYYY-MM-DD

### Completed
- [checkmark] Specific thing 1
- [checkmark] Specific thing 2

### Skipped / Cut
- [reason] Specific thing

### Known issues
- [description] — to address on Day X

### Next session should
- Specific actionable next step
```

User: at the start of every session, ask Claude Code to read PROGRESS.md first.

---

## Part 7 — When to Stop and Ask

Claude Code, **stop and ask the user** before:
- Adding any dependency not in the original `requirements.txt` plan
- Deviating from the agent count or architecture in Part 2
- Skipping tests "just for this one"
- Building something not on today's day-plan
- Touching configuration files (`.env`, `alembic.ini`, `package.json`) in non-obvious ways
- Anything that would take more than 30 minutes of your context to do without confirming the user wants it

**Don't stop and ask** for:
- Routine code changes within the day's plan
- Adding standard files (`.gitignore`, `README` updates, type hints, docstrings)
- Fixing your own mistakes from earlier in the same session

---

## Part 8 — Defense Day Reminders

- Demo first, slides second. Panel attention is highest in the first 5 minutes.
- Show the failure case: ask a question, get bad SQL, edit it via HITL, get correct result. This *proves* HITL is the right design.
- Have local demo ready as backup if deployed version fails.
- If asked "did you use AI to build this?" — say yes, explain that you used Claude Code as a pair programmer, that you made all architectural decisions, and that you understand every line. Show you do by walking them through one agent file.

---

## Part 9 — Post-Defense Roadmap

Items built post-defense (see PROGRESS.md for details):

- ✅ AWS Athena connector — two modes (ingest into DuckDB + direct Athena query via boto3)
- ✅ Multi-tenancy / data isolation — `_dataset_ownership` table, ChromaDB `user_id` filter, user-prefixed table names
- ✅ Saved queries with inline re-execution — `POST /saved-queries/{id}/run`, results rendered on page
- ✅ Daily routines — define N questions, run all through LangGraph, view results per-question
- ✅ Rich LLM summaries — computed stats (min/max/avg/total), structured Markdown output
- ✅ Glossary visibility in chat — sidebar badge + green active banner
- ✅ Home page redesign — glassmorphism, stat cards, "how it works" explainer
- ✅ CSV filename versioning — `_v2`, `_v3` instead of overwriting
- ✅ Admin system — `ADMIN_EMAILS` env var, `isAdmin` in session, global Athena credentials
- ✅ Table metadata UI — column descriptions, KPI definitions, business context, join hints

Still to do (genuine future work):

- Docker-compose for local dev
- OAuth providers via NextAuth (Google, GitHub)
- Scheduled query reports + email delivery
- Anomaly/trend detection agent (5th specialist)
- Rate limiting / cost controls
- Observability (LangSmith integration)
- SSE streaming for real-time token output

---

## Final note to Claude Code

This file is long because the project is non-trivial and the user is solo. Treat it as an actual contract. If the user asks for something contradicting it, say something like:

> "Heads up — that contradicts MASTER_PROMPT.md Part 2 which locks [decision]. Want me to override for this session, or stick to the plan?"

The user explicitly chose locked decisions to prevent decision fatigue across 14 days. Help them keep their commitment.

When in doubt: read the file again. The plan is in here.
