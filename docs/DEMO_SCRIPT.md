# Demo Script — Business Assistant

**Total time target: 12 minutes (extended for post-defense features)**
Practice the core 8-minute flow (steps 1–7) for formal presentations. The full 12-minute script covers all features.

---

## Pre-demo checklist (5 minutes before)

- [ ] Backend running: `cd backend && uvicorn app.main:app --reload`
- [ ] Frontend running: `cd frontend && npm run dev`
- [ ] Browser open at `http://localhost:3001`
- [ ] Logged out (or use incognito tab)
- [ ] Terminal visible but minimized (for emergency)
- [ ] Screen resolution large enough — increase font size if presenting on projector

---

## Demo order

### 1. Home page and sign up (45 sec)

- Open `http://localhost:3001` — show the home page with gradient design
- Point out the stat cards (Datasets, Conversations, Active this week, Glossary terms)
- Show the "How it works" explainer section
- Click "Start Analysing" or navigate to Sign Up

**What to say:** "The home page shows a live summary of your workspace — how many datasets are connected, how active you've been, and whether your glossary is populated. Everything is clickable."

---

### 2. Ask a simple data question (1 min)

Type: **"Show me the top 5 products by total revenue"**

- Watch the "Thinking…" indicator
- A SQL approval panel appears in amber — pause here

**What to say:** "This is the first differentiator — Human-in-the-Loop approval. The system generated a SQL query but it hasn't run yet. I can review it, edit it, or reject it. This is implemented using LangGraph's `interrupt()` primitive, which suspends the graph mid-execution and serializes the state to the database."

- Point to the SQL explanation ("This query joins order_items with products…")
- Point to the SQL itself
- Click **Approve & run**

---

### 3. Show the chart and rich summary (45 sec)

- An interactive Plotly bar chart appears with product names and revenue
- Hover over bars to show tooltips
- Point out the "Download as CSV" button
- Scroll down to show the LLM summary — it should include a **Key finding**, statistics (highest/lowest/average), and notable patterns

**What to say:** "The approved SQL ran against DuckDB — an in-process analytical database. The Analysis Agent picked bar chart because we have categorical products and numeric revenue. Notice the summary includes specific numbers — max revenue, average — not just a vague sentence."

---

### 4. Demonstrate SQL edit (1 min 30 sec)

Type: **"How many orders were placed by customers from Germany?"**

- Approval panel appears
- Click **Edit SQL**
- Change `ship_country = 'Germany'` to `ship_country = 'France'`
- Click **Approve with edits**
- Show the result

**What to say:** "Here's what makes this practical — I don't just approve or reject. I can fix the SQL inline. This is the HITL flow that makes the system safe: the LLM generates, the human validates and optionally corrects, then it executes."

---

### 5. Glossary (1 min)

- Click **Glossary** in the sidebar — notice the badge if terms exist
- Click **Add term**:
  - Term: `high value order`
  - Definition: `any order with total freight above 100`
- Click **Add term** — entry appears in table
- Navigate back to chat (Back to Chat button)

**Notice the green banner at the top of chat:** "X glossary terms active — business definitions are applied to every query automatically."

Type: **"Show me all high value orders"**

- Approval panel shows SQL that references freight > 100

**What to say:** "This is the second differentiator — the Business Glossary. I defined 'high value order' and the system automatically injected that definition into the SQL generation prompt. The green banner confirms it's active. Non-technical users can encode their domain knowledge without writing code."

- Approve the query, show results

---

### 6. CSV upload (45 sec)

- Click **Upload CSV** in the header
- Upload any small CSV file
- "Uploaded → table upload_xxx (N rows)" message appears

Type: **"How many rows are in [table name]?"**

- Approve the generated SELECT COUNT query
- Show the result

**What to say:** "Users can upload their own data. The system ingests it into DuckDB, re-embeds the schema into ChromaDB so the tables are immediately discoverable, and you can ask questions about the new data within seconds."

- Upload the **same file again** — point out the table name becomes `_v2`

**What to say:** "Uploading the same file a second time creates a versioned table — `_v2` — instead of silently overwriting the original. Your data is never lost."

---

### 7. Saved Queries (1 min)

- After a successful query, click the **Save** button (bookmark icon)
- Name it something meaningful, e.g. "Top 5 products by revenue"
- Navigate to **Saved Queries** page from the sidebar

- Show the saved query card
- Click **Run** — results appear inline with a fresh chart
- Point out the "fresh" label on the results table

**What to say:** "Saved queries let you bookmark results you want to check regularly. You can re-run them right here — no need to go back to chat and re-approve the SQL. The system re-executes the stored SQL against the latest data."

---

### 8. Daily Routines (1 min)

- Navigate to **Routines** from the sidebar
- Click **New Routine** — name it "Daily Briefing"
- Add 3 questions:
  - "Total orders placed today"
  - "Top 3 products by revenue this week"
  - "Average order value"
- Click **Save**
- Click **Run All** — watch all 3 questions execute in sequence

**What to say:** "Daily routines let you define a set of recurring questions and run them all at once. Each question goes through the full pipeline — schema linking, SQL generation, execution, charting — and you see all results in one view. This is how you'd build a morning data briefing."

---

### 9. Chat history sidebar (30 sec)

- Click **+ New** in the sidebar — fresh chat
- Type a quick question, approve, see result
- Click on the previous conversation in the sidebar — messages reload

**What to say:** "Conversation history is persisted in Postgres. Every thread and message is stored, and the LangGraph checkpointer preserves the full agent state so we could resume an interrupted approval from a previous session."

---

### 10. Closing (30 sec)

**What to say:**

> "To summarize — I built a multi-agent system using LangGraph that solves three real problems with conversational analytics. It picks the right tables from a large schema using ChromaDB embeddings. It captures business-specific definitions in a user-managed glossary. And it asks the user to approve every SQL query before running it, using LangGraph's interrupt-and-resume primitive. Post-defense, the system gained AWS Athena integration for cloud data, saved queries with inline re-execution, daily routines for recurring analysis, and improved LLM summaries with actual statistics. The architecture is modular — each of these additions touched one file."

---

## Anticipated questions and answers

### "Why four agents? Why not one big LLM call?"

Each agent has a single responsibility that can be tested in isolation. The Schema Agent uses vector similarity search — that's not an LLM task. The SQL Agent needs temperature 0 and strict validation. The Analysis Agent picks chart types with a deterministic heuristic. One monolithic prompt would make all of these harder to test and debug.

### "How does the interrupt/resume actually work?"

LangGraph's `interrupt()` raises a special exception that suspends graph execution and serialises the full state to a checkpointer (Postgres in production). The API returns `status: "needs_approval"` with the draft SQL. When the user approves, the frontend POSTs to `/api/chat/resume`, which calls `graph.ainvoke(Command(resume=decision), config)`. LangGraph reloads the state and continues from exactly where it paused.

### "Why DuckDB and not just use Postgres for analytics?"

DuckDB runs in-process — zero network latency, native Pandas integration for CSV ingest, and a SQL dialect compatible with AWS Athena for cloud migration. Postgres is optimised for transactional workloads; DuckDB is a column-oriented analytical engine that outperforms Postgres on aggregations by 10-100x on larger datasets.

### "How does Athena integration work?"

There are two modes. Ingest mode downloads table data from Athena into DuckDB locally — then queries run at DuckDB speed. Direct mode registers the table name in DuckDB but routes execution to Athena via boto3, returning results through the same analysis pipeline. Direct mode is better for large tables where you don't want to copy data.

### "Why not just use ChatGPT with code interpreter?"

ChatGPT executes code autonomously. This system keeps the human in the loop by design — the user reviews every query before it runs. That's appropriate for business data where a wrong aggregation could inform a bad business decision. The HITL mechanism is the core differentiator.

### "How do you prevent one user from seeing another user's data?"

Every DuckDB table is prefixed with the user's ID (`u{user_prefix}_{filename}`), and a `_dataset_ownership` table tracks which user owns which table. The schema agent calls `describe_user_tables(user_id)` which only returns that user's tables. ChromaDB is queried with `where={"user_id": user_id}` so even semantic search is scoped. Every API endpoint checks ownership before read or write.

### "Did you use AI to build this?"

Yes — I used Claude Code as a pair programmer throughout the build. I made all architectural decisions, wrote the system design, and understand every file. The LangGraph interrupt/resume mechanism, ChromaDB integration, and Athena integration are all things I can walk through line by line. Using AI as a coding assistant is like using a fast IDE — it doesn't change who owns the design.

### "What's next after this?"

The system has a clear extension path: LangSmith tracing for observability, a 5th anomaly-detection agent, scheduled routine reports with email delivery, and pgvector to replace ChromaDB. The auth system already has an admin role that can be expanded for full multi-tenant SaaS.

---

## Failure fallback plan

If the backend crashes during the demo:

1. Restart: `cd backend && uvicorn app.main:app --reload` (takes ~5 seconds)
2. If DB is corrupted: `cd backend && rm business_assistant.db dev.db` then restart
3. If the LLM key is rate-limited: show the approval panel from a previous run in chat history
4. If the frontend fails: `cd frontend && npm run dev` (takes ~10 seconds)
5. If Athena is not configured: stick to DuckDB flow — all core features work without Athena

Always have the terminal minimized but accessible.
