# Defense Slides — Business Assistant
# 8 slides · aim for 8 minutes total

Copy each slide into PowerPoint / Google Slides.
Keep design minimal: dark background, white text, one diagram per slide.
Largest font you're comfortable with — panel reads from the back.

---

## SLIDE 1 — Title (30 sec)

**Heading:**
Business Assistant
A Multi-Agent Conversational Analytics System

**Sub-heading:**
Natural language → SQL → Human approval → Interactive chart

**Bottom line:**
[Your name] · BS Information Technology · [University] · [Date]

**What to say:**
"I built a system that lets non-technical business users ask questions about their data in plain English, review the generated SQL before it runs, and see the results as an interactive chart. The core of the system is a multi-agent pipeline built on LangGraph."

---

## SLIDE 2 — The Problem (45 sec)

**Heading:** The Problem

**Three bullets:**
- Business analysts need data insights but can't write SQL
- Giving LLMs direct database access is dangerous — no guardrails
- Generic chatbots don't understand company-specific terminology

**One line below:**
→ We need natural language → data, with human oversight, and domain knowledge built in.

**What to say:**
"Every company has non-technical people who need data to make decisions but can't write SQL. The obvious solution — give an AI direct database access — is dangerous. A wrongly generated query could aggregate data incorrectly and lead to a bad business decision. And generic LLMs don't know what your company means by 'revenue' or 'churn'. This system solves all three problems."

---

## SLIDE 3 — Three Differentiators (1 min)

**Heading:** Three Differentiators

**Table or three columns:**

| | What | Benefit |
|---|---|---|
| 1 | Schema linking with embeddings | Only relevant tables sent to LLM — accurate as schema grows |
| 2 | Business glossary | User-defined terms injected into every prompt automatically |
| 3 | Human-in-the-loop SQL approval | Every query reviewed before it touches data |

**What to say:**
"The system has three things that make it more than an LLM wrapper. First, it uses ChromaDB vector embeddings to pick only the relevant tables rather than dumping the entire database schema into the prompt. Second, users maintain a business glossary — if 'revenue' means 'gross minus returns' at your company, you define that once and it's applied to every query. Third, every generated SQL query pauses for human review using LangGraph's interrupt primitive. The user sees the query, can edit it, and only then does it execute."

---

## SLIDE 4 — Architecture (1 min 30 sec)

**Heading:** System Architecture

**Diagram (draw as boxes with arrows):**

```
User question
      │
      ▼
 Supervisor          ← classifies intent (keyword routing)
      │
      ▼
 Schema Agent        ← ChromaDB semantic search → relevant tables
      │
      ▼
 SQL Agent           ← LLM generates SELECT SQL
      │
   interrupt()  ◄─── graph pauses, API returns "needs_approval"
      │
   User reviews / edits / rejects
      │
 POST /chat/resume
      │
      ▼
 Analysis Agent      ← executes SQL on DuckDB, picks chart type
      │
      ▼
 Interactive chart + summary
```

**Bottom strip (tech logos or text):**
LangGraph · FastAPI · DuckDB · ChromaDB · Next.js · PostgreSQL

**What to say:**
"The pipeline has four agents. The Supervisor does keyword routing — no LLM call, fast and deterministic. The Schema Agent uses ChromaDB to find which tables are relevant to the question. The SQL Agent generates a SELECT query and then — this is the key — calls interrupt(), which suspends the LangGraph graph mid-execution and sends the draft SQL back to the user for review. Only after approval does the Analysis Agent execute the SQL and build the chart."

---

## SLIDE 5 — HITL Deep Dive (1 min)

**Heading:** Human-in-the-Loop: How It Works

**Two-column layout:**

Left — Code snippet:
```python
# SQL Agent pauses here
decision = interrupt({
    "draft_sql": sql,
    "sql_explanation": explanation,
})

# Resumes here after user acts
action = decision["action"]  # approve | reject | edit
```

Right — What the user sees:
- Amber approval panel in the chat UI
- SQL with syntax highlighting
- Plain-English explanation
- Approve / Edit / Reject buttons

**What to say:**
"LangGraph's interrupt() is a first-class primitive. It raises a special signal that suspends the graph and serialises the complete state — all messages, the schema context, everything — to the PostgreSQL checkpointer. The API returns 'needs_approval'. When the user clicks Approve, the frontend POSTs to /chat/resume, LangGraph reloads the state and continues from exactly where it paused. If the user edits the SQL first, the edited version is validated and used instead."

---

## SLIDE 6 — Results (45 sec)

**Heading:** What Was Built

**Two columns:**

Left — Numbers:
- 75 automated tests — all passing
- 20-question accuracy eval harness
- 4 LangGraph agents
- 11 REST API endpoints
- 14 days, solo build

Right — Features shipped:
- JWT auth (signup / login)
- Natural language → SQL → chart
- HITL SQL approval with inline edit
- CSV upload → instant query
- Business glossary CRUD
- Chat history sidebar
- Dark mode

**What to say:**
"The system was built in 14 days as a solo project. It has 75 automated tests covering every endpoint and every agent, an accuracy eval harness with 20 ground-truth question-answer pairs against the sample dataset, and all the features you'd expect in a production analytics tool."

---

## SLIDE 7 — Live Demo (3 min)

**Heading:** Live Demo

**Bullet list (your cue card during the demo):**
1. Sign up → redirects to /chat
2. Ask: "Show me the top 5 products by total revenue"
3. SQL approval panel → Approve & run → bar chart
4. Ask: "How many orders shipped to Germany?" → Edit SQL → Approve with edits
5. Glossary → Add term → back to chat → ask using the term
6. Upload CSV → ask question about it
7. Sidebar → load previous conversation

**What to say before starting:**
"Let me show you the system working end to end. I'll start by signing up, which proves the auth flow works, then ask a data question that goes through all four agents."

*(Follow DEMO_SCRIPT.md exactly from here)*

---

## SLIDE 8 — Future Work + Questions (30 sec)

**Heading:** What's Next

**Left column — Future work:**
- AWS Athena connector (same interface, swap DuckDB)
- 5th agent: Anomaly & Trend Detection
- Scheduled reports via email
- LangSmith observability integration
- Docker-compose for local dev
- Multi-tenancy with row-level security

**Right column — large text:**
Questions?

**What to say:**
"The architecture is designed for extension. Swapping DuckDB for AWS Athena is a one-file change — the DataConnector interface is already abstracted. Adding a 5th agent for anomaly detection wouldn't touch the existing four. And LangSmith integration for full prompt/response tracing is a one-line change to the LLM initialisation."

*(Then open to questions — refer to DEMO_SCRIPT.md for anticipated Q&A)*

---

## Slide design notes

- **Font:** Inter or Helvetica, minimum 28pt body, 48pt headings
- **Colour:** Dark background (#0f172a), white text, amber accent (#f59e0b) for HITL slides
- **Code blocks:** Use monospace font, dark code box (no need to syntax highlight)
- **Diagrams:** Draw boxes by hand in Slides or use simple shapes — no screenshots of code
- **Logo strip:** Put tech logos small at the bottom of the architecture slide only
- **No bullet walls:** Maximum 4 bullets per slide; one idea per bullet
- **Timing chip:** Put the target time in small text at the bottom of each slide (e.g. "1:30") so you self-pace during practice

---

## 30-second answers (memorise these)

**"Why three agents, not one?"**
Each agent has a single job that can be tested in isolation. Schema search is a vector similarity task, not an LLM task. SQL generation needs temperature zero. Chart selection is a deterministic heuristic. One monolithic prompt would be impossible to test and debug.

**"How does interrupt/resume work?"**
LangGraph's interrupt() raises a signal that suspends the graph and checkpoints all state to Postgres. The API returns 'needs_approval'. When the user approves, the frontend calls /chat/resume, which passes Command(resume=decision) to LangGraph, which reloads state and continues from the suspension point.

**"Why DuckDB not Postgres for analytics?"**
DuckDB is a column-oriented in-process engine. Zero network latency, native Pandas integration for CSV uploads, and its SQL dialect is compatible with AWS Athena for future cloud migration. Postgres is a row store optimised for transactions — it's 10–100x slower on GROUP BY aggregations.

**"Why not ChatGPT with code interpreter?"**
ChatGPT executes autonomously. This system keeps humans in the loop by design — every query is reviewed before it touches data. That's the right choice for business analytics where a wrong aggregation could inform a bad decision.

**"Did you use AI to build this?"**
Yes — Claude Code as a pair programmer. I made every architectural decision, wrote the system design, and understand every file. I can walk through any agent or endpoint line by line. Using AI as a coding assistant is like using a fast IDE — it doesn't change who owns the design.
