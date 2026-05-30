# Architecture — Business Assistant

## 1. System overview

The Business Assistant is a **multi-agent analytics system** built on LangGraph. Users submit natural-language questions; the system routes the question through a chain of specialist agents, pauses for human approval of the generated SQL, executes the approved query against DuckDB or AWS Athena, and returns an interactive chart with a rich plain-English summary.

Three architectural decisions set this apart from a simple LLM wrapper:

1. **Schema linking with embeddings** — Only the relevant tables are sent to the LLM, not the entire schema. This keeps prompts short and improves accuracy as the schema grows.
2. **Business glossary** — Domain-specific definitions ("revenue = net of returns") are stored per-user in Postgres and automatically injected into SQL generation prompts.
3. **Human-in-the-loop (HITL) SQL approval** — The graph pauses mid-execution using LangGraph's `interrupt()` primitive. The user reviews, edits, or rejects the SQL before it touches any data.

---

## 2. Agent design

### Why a Supervisor + Specialists pattern?

LangChain's recommended pattern for multi-agent systems is a **Supervisor that routes to specialist sub-agents exposed as tools**. This was chosen because:

- Each specialist has a single, testable responsibility
- The Supervisor can grow routing logic without touching specialist code
- LangGraph checkpoints state between agents, so HITL mid-graph is natural

### The four agents

```
User question
      │
      ▼
┌─────────────┐
│  Supervisor  │  Classifies intent (data question vs. greeting)
└──────┬──────┘  Routes to schema or answers directly
       │
       ▼
┌─────────────┐
│ Schema Agent │  Finds relevant tables using ChromaDB semantic search
└──────┬──────┘  Writes schema_context to shared state
       │         Scoped to current user's tables only
       ▼
┌─────────────┐
│  SQL Agent   │  Generates SELECT SQL using schema_context + glossary
└──────┬──────┘  For Athena direct: generates Presto-compatible SQL
       │         Validates (blocks DROP/DELETE/etc.), explains in English
       │
       │  interrupt() ◄── graph pauses here
       │  API returns { status: "needs_approval", draft_sql, sql_explanation }
       │
       │  User clicks Approve / Edit / Reject
       │  POST /api/chat/resume with decision
       │
       ▼
┌─────────────────┐
│ Analysis Agent  │  Routes by query_engine:
└─────────────────┘    • "duckdb" → execute via DuckDB (default)
       │               • "athena_direct" → execute via boto3 Athena
       │  Picks chart type, builds Plotly JSON, writes rich summary
       ▼
  Response to frontend
  { content, chart_json, query_results }
```

#### Supervisor (`app/agents/supervisor.py`)
- Keyword-based intent classification (no LLM call — fast and deterministic)
- Data keywords ("show", "count", "revenue", "top", etc.) → routes to Schema Agent
- Conversational input → replies directly without touching DuckDB

#### Schema Agent (`app/agents/schema_agent.py`)
- On startup: embeds all table+column descriptions into a ChromaDB ephemeral collection using `all-MiniLM-L6-v2`
- Per query: runs a similarity search filtered by `user_id` to find the top-K most relevant tables
- Falls back to returning all user tables if ChromaDB is unavailable
- `refresh_chroma()` is called after CSV uploads so new tables are immediately discoverable
- Uses `describe_user_tables(user_id)` — never `describe_all_tables()` — for multi-user isolation
- Applies `preloaded_metadata` from state to enrich schema context with business descriptions and KPI definitions

#### SQL Agent (`app/agents/sql_agent.py`)
- Calls `generate_sql(question, schema_context, glossary_context)` — temperature 0.0 for determinism
- Prompt includes: schema with sample rows, FK relationship hints, few-shot examples, glossary terms
- When `query_engine == "athena_direct"`: adds Presto SQL dialect instructions (no LIMIT without ORDER, CAST syntax, etc.)
- `validate_sql()` hard-blocks any non-SELECT statement using regex + sqlparse
- `explain_sql()` generates a plain-English explanation — temperature 0.3
- Calls `interrupt({"draft_sql": ..., "sql_explanation": ...})` — graph suspends
- On resume: handles `approve` / `reject` / `edit` decisions

#### Analysis Agent (`app/agents/analysis_agent.py`)
- Reads `query_engine` from state to decide execution path
- **DuckDB path** (default): executes via `execute_query(sql)` against in-process DuckDB
- **Athena direct path**: calls `athena_run_query(sql, creds)` via boto3; polls until complete
- Converts result to `list[dict]`, builds pandas DataFrame
- `pick_chart_type(df)`: heuristic — date column → line; two numerics → scatter; categorical + numeric → bar
- `build_plotly_figure(df, chart_type)` → `fig.to_json()` (sent to frontend as-is)
- `summarize_result(df, question)` — rich LLM summary with:
  - Up to 30 preview rows + computed stats (min/max/avg/total per numeric column)
  - Structured Markdown: **Key finding**, Notable patterns, Highlights
  - Temperature 0.3; falls back to row-count message if LLM fails

---

## 3. Shared state (`app/agents/state.py`)

All agents read and write a single `AgentState` TypedDict that LangGraph checkpoints between steps:

```python
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # full conversation history
    current_step: str        # "schema" | "schema_done" | "approved" | "done" | "sql_error"
    schema_context: dict     # { table_name: { schema: [...], sample: [...] } }
    draft_sql: str           # generated SQL (set after HITL approval)
    sql_explanation: str     # plain-English explanation
    query_results: list[dict]# result rows as dicts
    chart_json: str          # Plotly figure JSON string
    glossary_context: list[dict]  # [{ term, definition }, ...] loaded per-request
    error: str               # last error message, empty on success
    # Post-defense additions:
    user_id: str             # current user's ID — passed to schema agent for isolation
    selected_datasets: list[str]  # explicit dataset filter (empty = all user's tables)
    query_engine: str        # "duckdb" | "athena_direct"
    athena_creds: dict       # pre-loaded Athena credentials (avoids asyncio.run in thread)
    preloaded_metadata: dict # pre-loaded table metadata enrichment from Postgres
```

`add_messages` is a LangGraph reducer that appends new messages rather than replacing the list, preserving full conversation history across checkpoints.

---

## 4. Graph wiring (`app/agents/graph.py`)

```python
graph = StateGraph(AgentState)
graph.add_node("supervisor",      supervisor_node)
graph.add_node("schema_agent",    schema_agent_node)
graph.add_node("sql_agent",       sql_agent_node)      # contains interrupt()
graph.add_node("analysis_agent",  analysis_agent_node)

graph.set_entry_point("supervisor")
graph.add_conditional_edges("supervisor",    _route_supervisor)  # → schema_agent | END
graph.add_conditional_edges("schema_agent",  _route_schema)      # → sql_agent | END
graph.add_conditional_edges("sql_agent",     _route_sql)         # → analysis_agent | END
graph.add_edge("analysis_agent", END)
```

The `interrupt()` call inside `sql_agent_node` suspends the graph. LangGraph serialises the full state to the checkpointer (PostgreSQL in production, SQLite on Windows dev). When `POST /api/chat/resume` is called, `graph.ainvoke(Command(resume=decision), config)` resumes from the exact suspension point.

---

## 5. Data layer

### PostgreSQL (SQLAlchemy + asyncpg)
Stores all **operational data** — user accounts, conversation threads, message history, glossary entries, saved queries, routines, Athena configuration, and table metadata. Uses SQLAlchemy async ORM with UUID primary keys throughout.

### DuckDB (in-process)
Stores all **analytical data** — the built-in Northwind-inspired sample dataset and any user-uploaded CSVs. DuckDB runs in-process (no separate service) using a file-based database (`business_assistant.db`). It is ideal here because:
- Zero-latency analytical queries
- Native Pandas integration for CSV ingest
- SQL dialect compatible with AWS Athena for cloud migration

**Multi-user isolation**: The `_dataset_ownership` table tracks which `user_id` owns each table. All user-uploaded tables are prefixed `u{8-char-user-id}_{filename}`. The schema agent calls `describe_user_tables(user_id)` which joins `_dataset_ownership` to return only the current user's tables plus shared built-in tables.

**CSV versioning**: `ingest_csv()` calls `_next_versioned_name(base, user_id, conn)` before creating a table. If `sales` already exists for the user, the new upload becomes `sales_v2`, then `sales_v3`, etc. (up to `_v98`). No data is ever silently overwritten.

### AWS Athena (optional, via boto3)
Two integration modes:

**Ingest mode**: Query Athena's `information_schema`, download table data, and load it into DuckDB locally. The table is then queryable via the normal DuckDB path.

**Direct mode**: Register the table name in DuckDB's `_athena_direct_refs` view (schema only, no data copied). When a query runs, `query_engine == "athena_direct"` routes execution to `athena_run_query()` which:
1. Submits the query to the Athena REST API
2. Polls until `SUCCEEDED` or `FAILED`
3. Reads results from the S3 output bucket
4. Returns rows to the analysis agent

Athena credentials can be per-user (stored in `AthenaConfig` table with `user_id`) or global (stored with `user_id = "__global__"` by an admin). The chat endpoint pre-loads both and merges them; personal credentials take priority over global.

### ChromaDB (ephemeral, in-process)
Holds schema embeddings for semantic table search. Rebuilt at startup from DuckDB's `information_schema`. Ephemeral (in-memory) because it can always be reconstructed — no persistence required.

**User-scoped queries**: Every `search_schema()` call passes `where={"user_id": user_id}` as a metadata filter to ChromaDB so users never see each other's tables in search results.

---

## 6. API endpoints

### Core chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message; returns `done` or `needs_approval` |
| POST | `/api/chat/resume` | Resume after HITL decision (approve/edit/reject) |
| GET | `/api/threads` | List user's conversation threads |
| GET | `/api/threads/{id}/messages` | Load messages for a thread |

### Data management
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/datasets/upload` | Upload a CSV file |
| GET | `/api/datasets` | List uploaded datasets |
| POST | `/api/datasets/export` | Export query results as CSV |

### Knowledge
| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/glossary` | List / create glossary entries |
| PUT/DELETE | `/api/glossary/{id}` | Update / delete a glossary entry |
| GET/PUT | `/api/catalog/{key}` | Get / upsert table metadata (display name, description, context, join hints) |
| PUT | `/api/catalog/{key}/columns/{col}` | Upsert column metadata (description, KPI definition) |
| POST | `/api/catalog/{key}/enrich` | AI-powered auto-enrichment of descriptions |
| POST | `/api/catalog/{key}/sync-schema` | Sync column list from live DuckDB schema |

### Saved queries
| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/saved-queries` | List / save a query |
| POST | `/api/saved-queries/{id}/run` | Re-execute saved SQL, return fresh results + chart |
| DELETE | `/api/saved-queries/{id}` | Delete a saved query |

### Daily routines
| Method | Path | Description |
|--------|------|-------------|
| GET/POST | `/api/routines` | List / create a routine |
| PUT | `/api/routines/{id}` | Update routine (name + questions) |
| POST | `/api/routines/{id}/run` | Run all questions through LangGraph pipeline |
| DELETE | `/api/routines/{id}` | Delete a routine |

### Athena
| Method | Path | Description |
|--------|------|-------------|
| GET/PUT | `/api/athena/config` | Get / save Athena credentials |
| GET | `/api/athena/tables` | List Athena tables from information_schema |
| POST | `/api/athena/load` | Ingest an Athena table into DuckDB |
| POST | `/api/athena/direct` | Register Athena table for direct querying |
| DELETE | `/api/athena/tables/{name}` | Remove a locally registered Athena table |

---

## 7. Windows asyncio fix

LangGraph nodes run in a thread pool on Windows. PostgreSQL async operations (via asyncpg) work fine in the main event loop but crash when called inside `asyncio.run()` from a thread on Windows' ProactorEventLoop.

**Solution**: Pre-load all database-dependent data in the async FastAPI endpoint handler *before* calling `graph.ainvoke()`, then pass the data as initial state fields:

```python
# chat.py — async FastAPI handler
glossary = await db.execute(select(GlossaryEntry).where(...))
athena_cfg = await db.execute(select(AthenaConfig).where(...))
metadata = await db.execute(select(TableMetadata).where(...))

result = await graph.ainvoke({
    "messages": [...],
    "glossary_context": glossary_list,
    "athena_creds": athena_dict,
    "preloaded_metadata": metadata_dict,
    "user_id": current_user.id,
}, config)
```

The same pattern is applied in `routines.py` (`run_routine` endpoint) so that routine runs also work safely on Windows.

---

## 8. Authentication flow

```
Browser                     Frontend (Next.js)           Backend (FastAPI)
   │                               │                            │
   │─── POST /auth/login ─────────►│                            │
   │                               │─── POST /api/auth/login ──►│
   │                               │◄── { access_token } ───────│
   │                               │                            │
   │◄── session cookie ────────────│                            │
   │                               │                            │
   │─── GET /chat ────────────────►│ (middleware checks session) │
   │                               │                            │
   │─── POST /api/chat ───────────►│                            │
   │                               │─── Authorization: Bearer ──►│
   │                               │    {JWT token}              │
   │                               │◄── { thread_id, content } ──│
```

- FastAPI issues HS256 JWTs (24h expiry), secret from `JWT_SECRET` env var
- NextAuth stores the token in a server-side session cookie
- Every API call includes `Authorization: Bearer <token>` from `session.accessToken`
- Backend verifies the token on every protected endpoint via `get_current_user` dependency
- `isAdmin` flag is injected into the NextAuth JWT session from the backend `GET /auth/me` response

---

## 9. Security

| Control | Implementation |
|---------|---------------|
| Password hashing | bcrypt, cost factor 12 (direct `bcrypt` library, not passlib) |
| JWT | HS256, 24-hour expiry, secret from env |
| SQL injection prevention | All user SQL validated + blocked on non-SELECT; DuckDB is read-only analytical DB |
| Destructive SQL blocking | Hard regex block: DROP / DELETE / UPDATE / TRUNCATE / INSERT / ALTER / GRANT / REVOKE |
| Ownership checks | Every API endpoint checks `user_id == current_user.id` before read/write/delete |
| Multi-tenant data isolation | DuckDB `_dataset_ownership` + ChromaDB `user_id` metadata filter |
| CORS | Restricted to `localhost:3000` and `localhost:3001` in dev |
| Admin access | `ADMIN_EMAILS` env var controls which users can set global Athena credentials |

---

## 10. Key design decisions and trade-offs

| Decision | Chosen | Rejected | Why |
|----------|--------|----------|-----|
| Agent framework | LangGraph | LangChain AgentExecutor, CrewAI | First-class `interrupt()`, typed state, checkpointing |
| HITL mechanism | `interrupt()` + `Command(resume=)` | SSE streaming | Simpler API surface; full-response model sufficient |
| Analytical DB | DuckDB | Direct Postgres queries | In-process, zero latency, Athena-compatible SQL dialect |
| Vector store | ChromaDB local | Pinecone, pgvector | No external service; can reconstruct from schema on startup |
| LLM abstraction | `init_chat_model()` | Direct Anthropic SDK | One env-var change swaps providers (Gemini → Claude → OpenAI) |
| Auth | FastAPI JWT + NextAuth | Supabase, Auth0 | Full control, no vendor lock-in |
| Windows dev | SQLite checkpointer fallback | psycopg3 async | psycopg3 async incompatible with ProactorEventLoop on Windows |
| Multi-user DuckDB isolation | `_dataset_ownership` table + user-prefixed names | Separate DuckDB files per user | Single file, no per-user startup cost, simple joins |
| Athena integration | Two modes (ingest + direct) | Only one mode | Ingest = simple DuckDB workflow; direct = no data copy for large tables |
| CSV versioning | `_v2`, `_v3` suffix | Overwrite / reject | Never silently lose user data; easy to reference old versions |
