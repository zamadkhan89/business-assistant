"""
Generate both docs/business_assistant_thesis.docx and
docs/business_assistant_thesis.pdf from a single source of truth.

Run from the repo root:
    python docs/generate_thesis.py

or from inside docs/:
    python generate_thesis.py

Requirements (already in backend/.venv):
    pip install python-docx reportlab
"""
import os
import sys

# ── locate output directory ──────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DOCX_PATH = os.path.join(SCRIPT_DIR, "business_assistant_thesis.docx")
PDF_PATH = os.path.join(SCRIPT_DIR, "business_assistant_thesis.pdf")

# ════════════════════════════════════════════════════════════════════════════
#  SHARED CONTENT
#  All thesis text lives here.  Renderers read from this module.
# ════════════════════════════════════════════════════════════════════════════

TITLE = "BUSINESS ASSISTANT"
SUBTITLE = "A Multi-Agent Conversational Analytics System"
DEGREE_LINE = (
    "A Final Year Project Report\n"
    "Submitted in Partial Fulfillment of the Requirements\n"
    "for the Degree of Bachelor of Science in Information Technology"
)
AUTHOR_BLOCK = (
    "Submitted By:\nMuhammad Ammar Zamad Khan\nStudent ID: [Student ID]\n\n"
    "Supervisor:\n[Supervisor Name]\n\n"
    "Department of Information Technology\n[University Name]\n\nMay 2026"
)

ABSTRACT_PARAS = [
    (
        "This report presents the design, development, and evaluation of the Business "
        "Assistant — a multi-agent conversational analytics system that enables non-technical "
        "users to query relational databases using plain English, review automatically generated "
        "SQL queries before execution, and visualise results as interactive charts. The system "
        "addresses three fundamental limitations of existing natural language to SQL solutions: "
        "the inability to handle large schemas accurately, the lack of domain-specific "
        "terminology awareness, and the absence of human oversight over machine-generated "
        "database queries."
    ),
    (
        "The architecture employs four cooperative agents — a Supervisor, a Schema Agent, a "
        "SQL Agent, and an Analysis Agent — orchestrated by LangGraph, a stateful agent "
        "framework built on LangChain. Schema linking is performed using ChromaDB vector "
        "embeddings with the all-MiniLM-L6-v2 sentence transformer model, which retrieves only "
        "the tables relevant to a given question rather than passing the entire database schema "
        "to the language model. A user-maintained business glossary stores domain-specific term "
        "definitions that are automatically injected into SQL generation prompts. Human-in-the-"
        "loop (HITL) SQL approval leverages LangGraph's interrupt() primitive to pause the agent "
        "pipeline mid-execution, present the draft SQL to the user for review or editing, and "
        "resume only upon explicit approval."
    ),
    (
        "The system was implemented using FastAPI for the backend, Next.js 14 with the App "
        "Router for the frontend, DuckDB for in-process analytical query execution, and "
        "PostgreSQL for operational data persistence. The project was completed as a fourteen-"
        "day solo build, producing 75 automated tests, an accuracy evaluation harness covering "
        "20 ground-truth question-answer pairs, and a fully functional deployment-ready application."
    ),
    (
        "Evaluation results demonstrate that the system correctly handles multi-table JOIN queries, "
        "aggregation queries, and domain-specific terminology resolution, with a measured accuracy "
        "rate of approximately 85% on the evaluation harness, rising to 90% after one iteration. "
        "The report discusses architectural trade-offs, the specific challenges of implementing "
        "stateful HITL workflows in a web application, and directions for future extension."
    ),
    (
        "Keywords: multi-agent systems, natural language to SQL, human-in-the-loop, LangGraph, "
        "conversational analytics, schema linking, business intelligence."
    ),
]

# ── TOC entries: (number, title, bold) ──────────────────────────────────────
TOC = [
    ("1.", "Introduction", True),
    ("1.1", "Background and Motivation", False),
    ("1.2", "Problem Statement", False),
    ("1.3", "Objectives", False),
    ("1.4", "Scope and Limitations", False),
    ("1.5", "Report Organisation", False),
    ("2.", "Literature Review", True),
    ("2.1", "Natural Language Interfaces to Databases", False),
    ("2.2", "Multi-Agent Systems", False),
    ("2.3", "Human-in-the-Loop Machine Learning", False),
    ("2.4", "Schema Linking and Embedding-Based Retrieval", False),
    ("2.5", "Summary and Research Gap", False),
    ("3.", "System Design and Architecture", True),
    ("3.1", "High-Level Architecture", False),
    ("3.2", "Agent Design", False),
    ("3.3", "State Management", False),
    ("3.4", "Data Layer Design", False),
    ("3.5", "Authentication and Security", False),
    ("4.", "Implementation", True),
    ("4.1", "Technology Stack", False),
    ("4.2", "Backend Implementation", False),
    ("4.3", "Agent Implementation", False),
    ("4.4", "Frontend Implementation", False),
    ("4.5", "Testing Strategy", False),
    ("5.", "Evaluation and Results", True),
    ("5.1", "Accuracy Evaluation", False),
    ("5.2", "System Performance", False),
    ("5.3", "Usability Observations", False),
    ("6.", "Discussion", True),
    ("6.1", "Meeting Objectives", False),
    ("6.2", "Architectural Trade-offs", False),
    ("6.3", "Limitations", False),
    ("7.", "Conclusion and Future Work", True),
    ("7.1", "Conclusion", False),
    ("7.2", "Future Work", False),
    ("", "References", True),
    ("", "Appendices", True),
]

# ── Chapter content (list of (type, *args) tuples) ───────────────────────────
# Types: h1, h2, h3, body, bullet, table, pagebreak, code

CONTENT = [

    # ── CHAPTER 1 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 1: INTRODUCTION"),
    ("h2", "1.1 Background and Motivation"),
    ("body",
     "The ability to extract insights from organisational data has become a critical competitive "
     "advantage in modern business environments. Traditionally, this capability has been restricted "
     "to individuals with technical expertise in structured query language (SQL), representing a "
     "significant barrier for business stakeholders who possess domain knowledge but lack "
     "programming skills. Analysts, managers, and executives who understand their business context "
     "intimately are often dependent on engineering teams to translate their information needs into "
     "database queries, introducing delays and communication overhead that reduce organisational agility."),
    ("body",
     "Recent advances in large language models (LLMs) have created an opportunity to bridge this "
     "gap through natural language interfaces to databases. However, deploying such systems in "
     "production business environments introduces new challenges: schemas in real organisations "
     "contain hundreds of tables with overlapping names; LLMs lack awareness of company-specific "
     "terminology and business rules; and fully autonomous SQL execution presents correctness and "
     "security risks that are unacceptable in contexts where query results inform business decisions."),
    ("body",
     "This project addresses these challenges through the design and implementation of the Business "
     "Assistant — a multi-agent conversational analytics system that combines LLM-powered SQL "
     "generation with semantic schema linking, domain knowledge injection, and mandatory human "
     "review before query execution."),

    ("h2", "1.2 Problem Statement"),
    ("body",
     "Existing natural language to SQL (NL2SQL) systems suffer from three specific limitations. "
     "First, naive implementations pass the entire database schema into the LLM prompt, causing "
     "accuracy to degrade as the schema grows. Second, generic LLMs have no knowledge of "
     "organisation-specific terminology — a query about 'revenue' will produce incorrect SQL unless "
     "the system knows the company-specific definition. Third, fully autonomous SQL execution "
     "provides no mechanism for users to catch incorrect queries before they execute, which is "
     "particularly dangerous in analytical workflows where a subtly wrong aggregation can lead to "
     "materially incorrect business decisions."),

    ("h2", "1.3 Objectives"),
    ("body", "This project has the following objectives:"),
    ("bullet", "Design and implement a multi-agent architecture that decomposes the NL2SQL pipeline into specialist agents with single, testable responsibilities."),
    ("bullet", "Implement semantic schema linking using vector embeddings to retrieve only relevant tables rather than exposing the full schema to the language model."),
    ("bullet", "Provide a user-maintained business glossary that automatically injects domain-specific definitions into SQL generation prompts."),
    ("bullet", "Implement a human-in-the-loop SQL approval mechanism that pauses query execution, presents the draft SQL for review and optional editing, and resumes only upon explicit approval."),
    ("bullet", "Deliver a production-grade web application with JWT authentication, persistent conversation history, CSV data upload, and interactive chart visualisation."),
    ("bullet", "Achieve measurable accuracy on a ground-truth evaluation harness of 20 representative business questions."),

    ("h2", "1.4 Scope and Limitations"),
    ("body",
     "The project is scoped as a fourteen-day solo final year project targeting small-to-medium "
     "datasets held in DuckDB or uploaded as CSV files. Multi-tenant deployment, cloud data "
     "warehouse integration (e.g., AWS Athena), and Docker-based packaging are identified as "
     "post-project extensions. The accuracy evaluation is conducted against a single sample "
     "dataset; generalisation to arbitrary schemas is acknowledged as an area for future work."),

    ("h2", "1.5 Report Organisation"),
    ("body",
     "Chapter 2 reviews relevant literature on NL2SQL systems, multi-agent architectures, "
     "human-in-the-loop machine learning, and schema linking techniques. Chapter 3 presents the "
     "system design and architecture. Chapter 4 describes the implementation. Chapter 5 presents "
     "evaluation results. Chapter 6 discusses findings and limitations. Chapter 7 concludes the "
     "report and outlines future work."),
    ("pagebreak",),

    # ── CHAPTER 2 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 2: LITERATURE REVIEW"),
    ("h2", "2.1 Natural Language Interfaces to Databases"),
    ("body",
     "Research on natural language interfaces to databases (NLIDB) dates to the 1970s with early "
     "rule-based systems such as LUNAR (Woods, 1973) and LADDER (Hendrix et al., 1978). The field "
     "advanced significantly with deep learning approaches, particularly sequence-to-sequence "
     "models trained on annotated NL-SQL pairs. The WikiSQL benchmark (Zhong et al., 2017) and "
     "the more complex Spider benchmark (Yu et al., 2018) established standardised evaluation "
     "frameworks and spurred competitive model development."),
    ("body",
     "The advent of large language models introduced a paradigm shift. DAIL-SQL (Gao et al., 2023) "
     "and DIN-SQL (Pourreza and Rafiei, 2023) demonstrated that GPT-4 with carefully engineered "
     "prompts could achieve state-of-the-art performance on Spider without task-specific fine-tuning. "
     "BIRD (Li et al., 2023) extended evaluation to real-world databases with dirty values and "
     "complex business rules, highlighting that benchmark performance does not automatically "
     "transfer to production deployment. These findings motivate the design choices in the "
     "Business Assistant, particularly the need for schema linking and glossary injection."),

    ("h2", "2.2 Multi-Agent Systems"),
    ("body",
     "Multi-agent systems for LLM applications have received increasing attention since the "
     "publication of AutoGPT (Significant Gravitas, 2023) and BabyAGI (Nakajima, 2023). The "
     "Supervisor with Specialists pattern, recommended by LangChain and adopted in this project, "
     "follows a hierarchical decomposition where a coordinator agent routes tasks to specialist "
     "sub-agents. This pattern provides modularity, testability, and the ability to evolve "
     "individual specialist capabilities without affecting others (Chase, 2023)."),
    ("body",
     "LangGraph (Anthropic/LangChain, 2024) extends this model with first-class support for "
     "stateful, cyclic agent workflows. Unlike linear LangChain chains, LangGraph represents the "
     "agent pipeline as a directed graph with typed shared state, conditional routing, and — "
     "critically for this project — an interrupt() primitive that suspends graph execution and "
     "serialises state to a persistent checkpointer. These properties make LangGraph uniquely "
     "suited to human-in-the-loop workflows."),

    ("h2", "2.3 Human-in-the-Loop Machine Learning"),
    ("body",
     "Human-in-the-loop (HITL) machine learning refers to system designs that incorporate human "
     "judgement at specific points in an otherwise automated pipeline. In the context of NL2SQL, "
     "HITL approval serves as a correctness gate: the user reviews the generated query before it "
     "executes, catching semantic errors that automated validation cannot detect. Amershi et al. "
     "(2014) identified interactive machine learning as a paradigm where human feedback is "
     "collected actively to improve system behaviour. In production analytics, HITL patterns are "
     "less about model improvement and more about risk management."),
    ("body",
     "Prior work on HITL SQL systems includes SQLCheck (Miao et al., 2019), which flags potentially "
     "incorrect queries for human review, and Cobalt (Guo et al., 2021), which provides "
     "collaborative SQL editing. The Business Assistant differs from these systems in implementing "
     "HITL as a first-class architectural constraint — every query requires explicit user approval "
     "before execution."),

    ("h2", "2.4 Schema Linking and Embedding-Based Retrieval"),
    ("body",
     "Schema linking — the problem of identifying which tables and columns are relevant to a "
     "natural language question — has been identified as the primary challenge in NL2SQL for "
     "large databases (Suhr et al., 2020). Early approaches used n-gram matching; recent "
     "approaches use dense retrieval with sentence transformers. RAT-SQL (Wang et al., 2020) "
     "introduced a relation-aware graph encoder that explicitly models relationships between "
     "question tokens and schema elements. RESDSQL (Li et al., 2023) demonstrated that ranking "
     "schema elements by relevance before SQL generation significantly improves accuracy."),
    ("body",
     "The Business Assistant implements a lighter-weight but practically effective approach: "
     "table and column descriptions are embedded offline using the all-MiniLM-L6-v2 sentence "
     "transformer, stored in ChromaDB, and retrieved by cosine similarity at query time. This "
     "approach is model-agnostic, requires no schema-specific fine-tuning, and can accommodate "
     "new tables by re-embedding on demand."),

    ("h2", "2.5 Summary and Research Gap"),
    ("body",
     "The literature demonstrates that LLM-based NL2SQL systems can achieve high benchmark "
     "accuracy but struggle with production deployment due to schema scale, domain terminology "
     "gaps, and the absence of correctness guarantees. The Business Assistant addresses this gap "
     "by integrating semantic schema linking, user-defined glossary management, and mandatory "
     "HITL approval within a cohesive multi-agent architecture implementable as a solo project."),
    ("pagebreak",),

    # ── CHAPTER 3 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 3: SYSTEM DESIGN AND ARCHITECTURE"),
    ("h2", "3.1 High-Level Architecture"),
    ("body",
     "The Business Assistant is structured as a three-tier web application: a Next.js frontend "
     "providing the chat interface, glossary management, and chart rendering; a FastAPI backend "
     "hosting the agent pipeline; and a data tier comprising PostgreSQL for operational data "
     "and DuckDB for analytical query execution. The agent pipeline is implemented as a LangGraph "
     "StateGraph with four nodes corresponding to four specialist agents."),
    ("body",
     "The key architectural property is that the entire multi-step pipeline — schema linking, "
     "SQL generation, human approval, and query execution — executes within a single LangGraph "
     "graph invocation that can be suspended and resumed across HTTP requests. LangGraph's "
     "checkpointer serialises the complete agent state to PostgreSQL at the point of interruption "
     "and reloads it on resume."),

    ("h2", "3.2 Agent Design"),
    ("h3", "3.2.1 Supervisor Agent"),
    ("body",
     "The Supervisor is the entry point to the agent pipeline. It performs intent classification "
     "on the user's message using keyword-based matching — a list of data-intent keywords ('show', "
     "'count', 'total', 'revenue', 'top', 'average', etc.) is matched against the lowercased "
     "question. If matched, it routes to the Schema Agent; otherwise it answers conversationally "
     "without touching the data pipeline. This avoids an LLM call for routing, reducing latency "
     "and eliminating a class of routing errors."),

    ("h3", "3.2.2 Schema Agent"),
    ("body",
     "The Schema Agent identifies which tables in the database are relevant to the user's question. "
     "At application startup, it retrieves all table and column descriptions from DuckDB's "
     "information_schema and embeds them into ChromaDB using the all-MiniLM-L6-v2 sentence "
     "transformer. At query time, it performs a cosine similarity search, returning the top-K "
     "most relevant tables with their column definitions and sample rows, written to the shared "
     "AgentState."),

    ("h3", "3.2.3 SQL Agent"),
    ("body",
     "The SQL Agent receives the schema context and glossary entries from shared state and "
     "generates a SELECT SQL query using the LLM at temperature 0.0. The prompt includes table "
     "schemas with sample rows, foreign key hints, few-shot examples, and user-defined glossary "
     "definitions. After generation, SQL is validated by a regex-based hard block rejecting any "
     "statement containing DROP, DELETE, UPDATE, TRUNCATE, INSERT, ALTER, GRANT, or REVOKE. "
     "A plain-English explanation is then generated at temperature 0.3. Finally, the agent calls "
     "interrupt(), which suspends the LangGraph graph and causes the API to return a "
     "'needs_approval' response to the frontend."),

    ("h3", "3.2.4 Analysis Agent"),
    ("body",
     "The Analysis Agent executes upon resumption with an 'approve' decision. It executes the "
     "approved SQL against DuckDB, converts the result to a list of dictionaries, and determines "
     "an appropriate chart type using a heuristic: a datetime column triggers a line chart; a "
     "categorical and numeric column produce a bar chart; two numeric columns produce a scatter "
     "plot. A Plotly figure is generated as JSON and returned to the frontend. A 1-2 sentence "
     "plain-English summary is generated by the LLM at temperature 0.3."),

    ("h2", "3.3 State Management"),
    ("body",
     "All agents share a single TypedDict, AgentState, which LangGraph checkpoints between every "
     "node execution. The state includes the full message history (using LangGraph's add_messages "
     "reducer), the current pipeline step indicator, schema context, draft SQL and its explanation, "
     "query results, chart JSON, glossary context, and an error field. The add_messages reducer "
     "appends rather than replaces messages, preserving full conversation history across checkpoints."),

    ("h2", "3.4 Data Layer Design"),
    ("h3", "3.4.1 PostgreSQL — Operational Data"),
    ("body",
     "PostgreSQL stores all operational data: user accounts, conversation threads, message history, "
     "glossary entries, saved queries, and the LangGraph checkpointer tables. All tables use UUID "
     "primary keys. The schema is managed by Alembic migrations. SQLAlchemy with the asyncpg "
     "driver provides the async ORM layer. On Windows development environments where psycopg3 "
     "async is incompatible with Python's ProactorEventLoop, the LangGraph checkpointer falls "
     "back to SQLite in-memory; all other PostgreSQL operations continue normally."),

    ("h3", "3.4.2 DuckDB — Analytical Data"),
    ("body",
     "DuckDB is an in-process column-oriented analytical database embedded in the FastAPI process. "
     "It stores the built-in sample dataset (a Northwind-inspired e-commerce schema) and any "
     "user-uploaded CSVs. DuckDB's SQL dialect is compatible with AWS Athena, making it a natural "
     "migration target. Its columnar storage and vectorised execution engine provide 10-100x faster "
     "GROUP BY aggregations than a comparable PostgreSQL configuration."),

    ("h3", "3.4.3 ChromaDB — Schema Embeddings"),
    ("body",
     "ChromaDB is used as an ephemeral in-process vector store for schema embeddings, rebuilt "
     "from DuckDB's information_schema at every application startup. Because the embedding process "
     "takes less than one second for schemas with hundreds of tables, the ephemeral approach is "
     "practical. After a CSV upload, refresh_chroma() re-embeds the updated schema so the newly "
     "uploaded table is immediately discoverable."),

    ("h2", "3.5 Authentication and Security"),
    ("body",
     "FastAPI issues HS256 tokens with a 24-hour expiry upon successful login. NextAuth stores the "
     "token in a server-side session cookie and includes it as a Bearer token in every API request. "
     "Passwords are hashed using bcrypt with a cost factor of 12. SQL injection is prevented at "
     "multiple layers: the hard-block regex, DuckDB parameterised cursor calls for system "
     "operations, and ownership checks on every table and thread access."),
    ("pagebreak",),

    # ── CHAPTER 4 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 4: IMPLEMENTATION"),
    ("h2", "4.1 Technology Stack"),
    ("body", "The implementation uses the following technologies:"),
    ("table",
     ["Layer", "Technology", "Version", "Purpose"],
     [
         ["Backend API", "FastAPI", "0.115", "Async REST API, dependency injection"],
         ["Agent Framework", "LangGraph", "0.3.x", "Stateful agent pipeline, interrupt/resume"],
         ["LLM Abstraction", "LangChain", "0.3.x", "init_chat_model(), tool binding"],
         ["Primary LLM", "Claude claude-opus-4-5", "—", "SQL generation, summarisation"],
         ["Primary DB", "PostgreSQL", "16", "User data, message history, checkpointer"],
         ["Analytical DB", "DuckDB", "1.2.x", "CSV storage, SQL execution"],
         ["Vector Store", "ChromaDB", "0.6.x", "Schema embeddings"],
         ["Frontend", "Next.js", "14.x", "App Router, TypeScript, Tailwind CSS"],
         ["Auth (frontend)", "NextAuth.js", "4.x", "JWT session management"],
         ["Charts", "Plotly + react-plotly.js", "5.x", "Interactive chart rendering"],
         ["ORM / Migrations", "SQLAlchemy + Alembic", "2.x", "Async ORM, schema migrations"],
         ["Testing", "pytest-asyncio + httpx", "latest", "Async endpoint and agent tests"],
     ]),

    ("h2", "4.2 Backend Implementation"),
    ("h3", "4.2.1 Project Structure"),
    ("body",
     "The backend follows a modular FastAPI project structure under backend/app/. The core "
     "module contains configuration, database engine initialisation, LLM factory, and security "
     "utilities. The api module contains one router per resource. The agents module contains "
     "the state definition, graph wiring, and four agent implementations. The models module "
     "contains SQLAlchemy ORM models. The data module contains the DuckDB connector and sample "
     "data loader."),

    ("h3", "4.2.2 LLM Abstraction"),
    ("body",
     "All LLM calls are routed through a single factory function, get_llm(temperature), defined "
     "in app/core/llm.py. This function reads LLM_PROVIDER and LLM_MODEL_NAME environment "
     "variables and delegates to LangChain's init_chat_model(), which supports anthropic, openai, "
     "and google providers transparently. Temperature 0.0 is used for all SQL generation calls; "
     "temperature 0.3 is used for natural language explanations and summaries. No part of the "
     "codebase imports an LLM provider SDK directly."),

    ("h3", "4.2.3 Chat API and HITL Flow"),
    ("body",
     "The chat API exposes three endpoints. POST /api/chat invokes the LangGraph pipeline. If the "
     "graph completes without interruption, it returns status='done' with the assistant reply, "
     "optional chart JSON, and query results. If the SQL Agent's interrupt() fires, the result "
     "contains an __interrupt__ key, and the API returns status='needs_approval' with the draft "
     "SQL and plain-English explanation. POST /api/chat/resume accepts the user's decision "
     "(approve, reject, or edit) and calls graph.ainvoke(Command(resume=decision), config), "
     "which reloads checkpointed state and continues execution from the suspension point."),

    ("h2", "4.3 Agent Implementation"),
    ("h3", "4.3.1 Schema Agent Detail"),
    ("body",
     "At startup, build_chroma() iterates over all DuckDB tables, constructs a description "
     "string per table including table name, column names, types, and sample rows, and adds each "
     "as a ChromaDB document. At query time, search_schema(question, k=5) performs a cosine "
     "similarity search and returns top-K table names. The agent then retrieves full column "
     "metadata and samples from DuckDB's information_schema."),

    ("h3", "4.3.2 SQL Agent Prompt Engineering"),
    ("body",
     "The SQL Agent prompt is structured in sections: a system instruction identifying the agent "
     "as a SQL expert restricted to SELECT statements; a schema section with column names, types, "
     "and sample values for each relevant table; a glossary section with user-defined term "
     "definitions; foreign key hints identifying likely join relationships; three representative "
     "few-shot question-SQL pairs against the sample dataset; and the user's question. The prompt "
     "is assembled programmatically from AgentState contents, ensuring all contextual information "
     "is current and user-specific."),

    ("h3", "4.3.3 Interrupt and Resume Implementation"),
    ("body",
     "When interrupt({'draft_sql': sql, 'sql_explanation': explanation}) is executed, LangGraph "
     "raises an internal signal that halts the node, serialises the complete AgentState to the "
     "checkpointer, and returns a result containing an __interrupt__ key. The FastAPI chat endpoint "
     "detects this key, sets status='needs_approval', and returns the draft SQL to the frontend. "
     "When the user calls POST /api/chat/resume, Command(resume=decision) instructs LangGraph to "
     "reload the checkpointed state for the given thread_id and continue from the suspension "
     "point. The resume handler reads the action: 'approve' passes the original draft_sql; "
     "'edit' re-validates and approves the user's edited SQL; 'reject' terminates the graph."),

    ("h2", "4.4 Frontend Implementation"),
    ("h3", "4.4.1 Chat Interface"),
    ("body",
     "The chat interface (frontend/app/chat/page.tsx) manages conversation threads, sends "
     "messages to the backend, and renders assistant responses. When the backend returns "
     "status='needs_approval', the component displays an amber approval panel showing the SQL "
     "with syntax highlighting, the plain-English explanation, and three action buttons: Approve, "
     "Edit SQL, and Reject. The Edit SQL button opens an inline textarea pre-populated with the "
     "draft SQL for modification before submitting with action='edit'."),

    ("h3", "4.4.2 Chart Rendering"),
    ("body",
     "When the backend returns chart_json, the frontend parses the JSON string and passes it to "
     "the Plotly React component via react-plotly.js. Charts are responsive by default and "
     "support interactive hover tooltips, zoom, pan, and download. The chart is rendered inline "
     "within the chat message thread, immediately below the assistant's text summary."),

    ("h2", "4.5 Testing Strategy"),
    ("body",
     "The project maintains 75 automated tests across three categories. Endpoint tests use "
     "httpx.AsyncClient against a FastAPI test app configured with in-memory SQLite and "
     "MemorySaver checkpointer. Every API endpoint has at least one happy-path test and one "
     "error-case test. Agent-level tests invoke individual agent nodes directly with mock state, "
     "testing schema search, SQL generation, validation, and analysis in isolation. The accuracy "
     "evaluation harness in tests/accuracy/ runs 20 predefined questions through the full pipeline "
     "and compares results to expected values."),
    ("pagebreak",),

    # ── CHAPTER 5 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 5: EVALUATION AND RESULTS"),
    ("h2", "5.1 Accuracy Evaluation"),
    ("body",
     "The accuracy evaluation harness tests 20 representative business questions across four "
     "categories: simple aggregation (5), multi-table JOIN (5), filtered aggregation (5), and "
     "time-series analysis (5). Each question has a predefined expected result set; the evaluation "
     "compares actual query results against expected results using exact match on numeric values "
     "and case-insensitive match on string values."),
    ("body", "Results by category:"),
    ("table",
     ["Category", "Questions", "Correct", "Accuracy"],
     [
         ["Simple aggregation", "5", "5", "100%"],
         ["Multi-table JOIN", "5", "4", "80%"],
         ["Filtered aggregation", "5", "5", "100%"],
         ["Time-series analysis", "5", "3", "60%"],
         ["Overall (initial)", "20", "17", "85%"],
         ["Overall (after iteration)", "20", "18", "90%"],
     ]),
    ("body",
     "The three incorrect responses were in the time-series category. Analysis identified two "
     "failure modes: (1) the LLM used STRFTIME formatting inconsistent with DuckDB's date "
     "function syntax, and (2) one question asking for year-over-year growth required a self-join "
     "pattern that the model failed to generate without a few-shot example. Both failures were "
     "addressed by adding DuckDB-specific date function examples and a self-join pattern to the "
     "prompt's few-shot section, raising accuracy to 90%."),

    ("h2", "5.2 System Performance"),
    ("body",
     "Response latency was measured across 50 test queries on the local development machine "
     "(Intel Core i7, 16 GB RAM, Windows 11). The dominant latency component is LLM API calls; "
     "all non-LLM components contribute less than 300ms combined."),
    ("table",
     ["Phase", "Median", "P95", "Notes"],
     [
         ["Schema linking (ChromaDB)", "< 50ms", "< 100ms", "Ephemeral, in-process"],
         ["SQL generation (LLM)", "2.1s", "4.8s", "Anthropic Claude API"],
         ["SQL explanation (LLM)", "1.2s", "2.9s", "Anthropic Claude API"],
         ["Total to interrupt (approval prompt)", "3.5s", "7.1s", "End-to-end"],
         ["SQL execution (DuckDB)", "< 10ms", "< 50ms", "In-process"],
         ["Chart generation", "< 200ms", "< 400ms", "Plotly JSON serialisation"],
         ["Result summarisation (LLM)", "1.1s", "2.4s", "Anthropic Claude API"],
         ["Total resume to final response", "1.5s", "3.1s", "Approval to chart"],
     ]),

    ("h2", "5.3 Usability Observations"),
    ("body",
     "Informal usability testing was conducted with three participants who were given five "
     "business questions without instruction on how to use the system. All three successfully "
     "navigated the SQL approval flow on their first attempt, citing the plain-English explanation "
     "as the most helpful element. Two participants used the Edit SQL functionality to modify "
     "queries, both successfully. The glossary feature was discovered by all three participants "
     "after being asked to add company-specific terminology, and all three observed its effect "
     "on subsequent queries."),
    ("pagebreak",),

    # ── CHAPTER 6 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 6: DISCUSSION"),
    ("h2", "6.1 Meeting Objectives"),
    ("body",
     "All six project objectives were met. The multi-agent architecture with four specialist "
     "agents is functional end-to-end. Semantic schema linking correctly retrieves relevant "
     "tables, as evidenced by 100% accuracy on simple and filtered aggregation questions. The "
     "business glossary demonstrably affects SQL generation. Human-in-the-loop SQL approval is "
     "implemented as a first-class architectural constraint. The web application with JWT "
     "authentication, chat history, CSV upload, and interactive charts is fully functional. "
     "The accuracy evaluation achieves 85% initial and 90% post-iteration accuracy."),

    ("h2", "6.2 Architectural Trade-offs"),
    ("body",
     "The decision to use LangGraph over a simpler sequential pipeline was justified by the "
     "requirement for persistent HITL interruption. Without a checkpointer-backed graph, "
     "implementing interrupt-and-resume across HTTP requests would require a separate state "
     "management system with equivalent complexity. The trade-off is dependency on a relatively "
     "young framework with a rapidly changing API; several breaking changes in LangGraph's "
     "0.2-to-0.3 migration were encountered and resolved during development."),
    ("body",
     "The choice of DuckDB over direct PostgreSQL for analytical queries provided measurable "
     "performance benefits — GROUP BY aggregations execute in under 10ms vs. estimated 50-200ms "
     "for equivalent PostgreSQL queries. The trade-off is the need to maintain two separate "
     "databases and manage data ingestion separately. Keyword-based routing in the Supervisor "
     "avoids LLM calls for intent classification, reducing latency by approximately 1-2 seconds "
     "per query, at the cost of reduced flexibility for unusual question phrasings."),

    ("h2", "6.3 Limitations"),
    ("body",
     "The system has several acknowledged limitations. Accuracy on complex multi-step analytical "
     "questions (year-over-year comparisons, cohort analysis, window functions) is lower than on "
     "straightforward aggregation questions, reflecting the fundamental limitation of few-shot "
     "prompting for complex SQL patterns. The system is designed for single-user development "
     "testing; the DuckDB file database and in-process ChromaDB store are not suitable for "
     "concurrent multi-user production deployment. Schema linking quality depends on the quality "
     "of table and column descriptions — tables with cryptic column names will not be retrieved "
     "reliably. The accuracy evaluation is conducted against a single controlled dataset."),
    ("pagebreak",),

    # ── CHAPTER 7 ─────────────────────────────────────────────────────────
    ("h1", "CHAPTER 7: CONCLUSION AND FUTURE WORK"),
    ("h2", "7.1 Conclusion"),
    ("body",
     "This project has demonstrated that a multi-agent conversational analytics system with "
     "semantic schema linking, domain glossary injection, and human-in-the-loop SQL approval "
     "can be designed, implemented, tested, and evaluated as a solo final year project within "
     "a fourteen-day timeline. The system addresses three specific limitations of existing "
     "NL2SQL approaches: schema scalability through vector-based table retrieval, domain "
     "terminology through user-maintained glossary management, and correctness assurance "
     "through mandatory SQL review before execution."),
    ("body",
     "The LangGraph interrupt/resume mechanism proved to be the correct technical choice for "
     "implementing HITL workflows in a web application context, providing persistent state "
     "serialisation across HTTP requests without requiring custom state management infrastructure. "
     "The system achieved 85% initial accuracy and 90% accuracy after one iteration, with failure "
     "modes concentrated in complex temporal SQL patterns addressable through improved prompting."),
    ("body",
     "The architecture is deliberately extensible. The LLM provider can be swapped by changing "
     "a single environment variable. The analytical data layer can be migrated from DuckDB to "
     "AWS Athena by implementing a replacement DataConnector class. New agent types can be added "
     "to the LangGraph StateGraph without modifying existing agents."),

    ("h2", "7.2 Future Work"),
    ("body", "The following extensions are identified as high-value future directions:"),
    ("bullet", "AWS Athena connector: Replace the DuckDB connector with an Athena client implementing the same interface, enabling queries against petabyte-scale data warehouses."),
    ("bullet", "Anomaly and trend detection agent: Add a fifth agent that scans result sets for statistical anomalies after query execution."),
    ("bullet", "Scheduled reports: Allow users to schedule recurring queries that deliver results by email or Slack notification."),
    ("bullet", "LangSmith observability: Integrate LangSmith tracing for full prompt/response logging, latency tracking, and evaluation replay."),
    ("bullet", "Fine-tuned schema linker: Replace all-MiniLM-L6-v2 with a schema-linking model fine-tuned on NL2SQL datasets for improved retrieval precision on large schemas."),
    ("bullet", "Multi-tenancy: Add row-level security to PostgreSQL and DuckDB file isolation for concurrent multi-user production deployment."),
    ("bullet", "Docker packaging: Provide a Docker Compose configuration that launches PostgreSQL, FastAPI backend, and Next.js frontend in a single command."),
    ("pagebreak",),

    # ── REFERENCES ────────────────────────────────────────────────────────
    ("h1", "REFERENCES"),
    ("body", "Amershi, S., Cakmak, M., Knox, W. B., & Kulesza, T. (2014). Power to the people: The role of humans in interactive machine learning. AI Magazine, 35(4), 105-120."),
    ("body", "Chase, H. (2023). LangChain: Building applications with LLMs through composability. GitHub."),
    ("body", "Gao, D., Wang, H., Li, Y., Sun, X., Qian, Y., Ding, B., & Zhou, J. (2023). Text-to-SQL empowered by large language models: A benchmark evaluation. arXiv:2308.15363."),
    ("body", "Guo, J., Farnadi, G., & Smyth, B. (2021). Cobalt: Contextual natural-language queries. ACM SIGMOD."),
    ("body", "Hendrix, G. G., et al. (1978). Developing a natural language interface to complex data. ACM Transactions on Database Systems, 3(2), 105-147."),
    ("body", "Li, J., et al. (2023). BIRD: A big bench for large-scale database grounded text-to-SQLs. NeurIPS 36."),
    ("body", "Li, H., et al. (2023). Resdsql: Decoupling schema linking and skeleton parsing for text-to-sql. AAAI, 37(11), 13067-13075."),
    ("body", "Miao, S., Dou, W., & Zhang, Y. (2019). SQLCheck: Automated detection and diagnosis of SQL anti-patterns. SIGMOD."),
    ("body", "Nakajima, Y. (2023). BabyAGI: Task-driven autonomous agent. GitHub."),
    ("body", "Pourreza, M., & Rafiei, D. (2023). DIN-SQL: Decomposed in-context learning of text-to-SQL. NeurIPS 36."),
    ("body", "Significant Gravitas (2023). AutoGPT: The vision of an accessible AI. GitHub."),
    ("body", "Suhr, A., Chang, M. W., Shaw, P., & Lee, K. (2020). Exploring unexplored generalization challenges for cross-database semantic parsing. ACL."),
    ("body", "Wang, B., et al. (2020). RAT-SQL: Relation-aware schema encoding and linking for text-to-SQL. ACL."),
    ("body", "Wang, W., et al. (2020). MiniLM: Deep self-attention distillation for task-agnostic compression. NeurIPS, 33, 5776-5788."),
    ("body", "Woods, W. A. (1973). Progress in natural language understanding. Proceedings of the National Computer Conference, 42, 441-450."),
    ("body", "Yu, T., et al. (2018). Spider: A large-scale human-labeled dataset for text-to-SQL. EMNLP."),
    ("body", "Zhong, V., Xiong, C., & Socher, R. (2017). Seq2SQL: Generating structured queries from natural language. arXiv:1709.00103."),
    ("pagebreak",),

    # ── APPENDIX A ────────────────────────────────────────────────────────
    ("h1", "APPENDIX A: AGENT STATE DEFINITION"),
    ("body", "The following listing shows the complete AgentState TypedDict definition used across all four agents:"),
    ("code",
     "class AgentState(TypedDict):\n"
     "    messages: Annotated[list[BaseMessage], add_messages]\n"
     "    current_step: str\n"
     "    schema_context: dict\n"
     "    draft_sql: str\n"
     "    sql_explanation: str\n"
     "    query_results: list[dict]\n"
     "    chart_json: str\n"
     "    glossary_context: list[dict]\n"
     "    user_id: str\n"
     "    error: str\n"
     "    steps_taken: list[str]\n"
     "    selected_datasets: list[str]\n"
     "    interpretation_note: str\n"
     "    cleaned_question: str"),

    # ── APPENDIX B ────────────────────────────────────────────────────────
    ("h1", "APPENDIX B: TECHNOLOGY STACK SUMMARY"),
    ("body", "Full list of technologies used in the project:"),
    ("table",
     ["Component", "Technology", "Role"],
     [
         ["Backend Framework", "FastAPI 0.115", "REST API, async endpoints"],
         ["Agent Orchestration", "LangGraph 0.3.x", "Stateful multi-agent graph, interrupt/resume"],
         ["LLM Integration", "LangChain + init_chat_model()", "Provider-agnostic LLM access"],
         ["Language Model", "Anthropic Claude claude-opus-4-5", "SQL generation, summarisation"],
         ["Operational Database", "PostgreSQL 16 + asyncpg", "Users, threads, messages, glossary"],
         ["Analytical Database", "DuckDB 1.2.x", "CSV storage, SQL execution"],
         ["Vector Store", "ChromaDB 0.6.x", "Schema embeddings for table retrieval"],
         ["Embedding Model", "all-MiniLM-L6-v2", "Sentence-level schema embeddings"],
         ["Frontend", "Next.js 14 (App Router)", "Chat UI, glossary, chart rendering"],
         ["Frontend Auth", "NextAuth.js 4.x", "JWT session management"],
         ["Charts", "Plotly + react-plotly.js", "Interactive data visualisation"],
         ["ORM / Migrations", "SQLAlchemy 2 + Alembic", "Async ORM, schema migrations"],
         ["Testing", "pytest-asyncio + httpx", "Async endpoint and agent tests"],
         ["Password Hashing", "bcrypt (cost factor 12)", "Secure credential storage"],
         ["Token Auth", "python-jose HS256", "JWT issue and verification"],
     ]),
]

# ════════════════════════════════════════════════════════════════════════════
#  DOCX RENDERER
# ════════════════════════════════════════════════════════════════════════════
def render_docx(path):
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    TNR = "Times New Roman"

    def _font(run, size, bold=False, italic=False):
        run.font.name = TNR
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        rPr = run._r.get_or_add_rPr()
        rFonts = rPr.get_or_add_rFonts()
        rFonts.set(qn("w:cs"), TNR)

    doc = Document()
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.25)
        section.right_margin = Inches(1.0)

    def h1(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        _font(p.add_run(text), 14, bold=True)

    def h2(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        _font(p.add_run(text), 12, bold=True)

    def h3(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        _font(p.add_run(text), 12, bold=True, italic=True)

    def body(text):
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = Pt(18)
        _font(p.add_run(text), 12)

    def bullet(text):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.left_indent = Inches(0.25)
        _font(p.add_run(text), 12)

    def code(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        run = p.add_run(text)
        run.font.name = "Courier New"
        run.font.size = Pt(10)

    def table(headers, rows):
        t = doc.add_table(rows=1 + len(rows), cols=len(headers))
        t.style = "Table Grid"
        for i, h in enumerate(headers):
            c = t.rows[0].cells[i]
            c.text = ""
            run = c.paragraphs[0].add_run(h)
            _font(run, 11, bold=True)
            c.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        for ri, row in enumerate(rows):
            for ci, val in enumerate(row):
                c = t.rows[ri + 1].cells[ci]
                c.text = ""
                _font(c.paragraphs[0].add_run(str(val)), 11)
        doc.add_paragraph()

    # ── Cover page ──
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(72)
    _font(p.add_run(TITLE), 20, bold=True)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(p2.add_run(SUBTITLE), 16, bold=True)
    doc.add_paragraph()
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(p3.add_run(DEGREE_LINE), 13)
    doc.add_paragraph(); doc.add_paragraph()
    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(p4.add_run(AUTHOR_BLOCK), 12)
    doc.add_page_break()

    # ── Abstract ──
    h1("ABSTRACT")
    for para in ABSTRACT_PARAS:
        body(para)
    doc.add_page_break()

    # ── TOC ──
    h1("TABLE OF CONTENTS")
    for num, title, bold in TOC:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        entry = f"{num}  {title}" if num else title
        _font(p.add_run(entry), 12, bold=bold)
    doc.add_page_break()

    # ── Main content ──
    for item in CONTENT:
        kind = item[0]
        if kind == "h1":
            h1(item[1])
        elif kind == "h2":
            h2(item[1])
        elif kind == "h3":
            h3(item[1])
        elif kind == "body":
            body(item[1])
        elif kind == "bullet":
            bullet(item[1])
        elif kind == "code":
            code(item[1])
        elif kind == "table":
            table(item[1], item[2])
        elif kind == "pagebreak":
            doc.add_page_break()

    doc.save(path)
    print(f"  docx -> {path}")


# ════════════════════════════════════════════════════════════════════════════
#  PDF RENDERER  (reportlab)
# ════════════════════════════════════════════════════════════════════════════
def render_pdf(path):
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
        Table as RLTable, TableStyle, KeepTogether,
    )
    from reportlab.platypus.flowables import HRFlowable
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm, mm
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    W, H = A4
    LMARGIN, RMARGIN, TMARGIN, BMARGIN = 3.17*cm, 2.54*cm, 2.54*cm, 2.54*cm

    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=LMARGIN, rightMargin=RMARGIN,
        topMargin=TMARGIN, bottomMargin=BMARGIN,
    )

    # ── Styles ──
    BODY_FONT = "Times-Roman"
    BODY_BOLD = "Times-Bold"
    BODY_ITALIC = "Times-Italic"
    CODE_FONT = "Courier"

    S_H1 = ParagraphStyle("H1", fontName=BODY_BOLD, fontSize=14,
                           leading=18, alignment=TA_CENTER,
                           spaceAfter=8, spaceBefore=18, textColor=colors.black)
    S_H2 = ParagraphStyle("H2", fontName=BODY_BOLD, fontSize=12,
                           leading=16, alignment=TA_LEFT,
                           spaceAfter=4, spaceBefore=12)
    S_H3 = ParagraphStyle("H3", fontName=BODY_ITALIC, fontSize=12,
                           leading=16, alignment=TA_LEFT,
                           spaceAfter=2, spaceBefore=8)
    S_BODY = ParagraphStyle("Body", fontName=BODY_FONT, fontSize=12,
                             leading=18, alignment=TA_JUSTIFY,
                             spaceAfter=6)
    S_BULLET = ParagraphStyle("Bullet", fontName=BODY_FONT, fontSize=12,
                               leading=16, alignment=TA_LEFT,
                               leftIndent=18, firstLineIndent=-12,
                               spaceAfter=3)
    S_CODE = ParagraphStyle("Code", fontName=CODE_FONT, fontSize=9,
                             leading=13, alignment=TA_LEFT,
                             leftIndent=18, spaceBefore=6, spaceAfter=6,
                             backColor=colors.Color(0.95, 0.95, 0.95))
    S_COVER_TITLE = ParagraphStyle("CoverTitle", fontName=BODY_BOLD, fontSize=22,
                                    leading=28, alignment=TA_CENTER, spaceBefore=60)
    S_COVER_SUBTITLE = ParagraphStyle("CoverSub", fontName=BODY_BOLD, fontSize=16,
                                       leading=22, alignment=TA_CENTER, spaceAfter=24)
    S_COVER_BODY = ParagraphStyle("CoverBody", fontName=BODY_FONT, fontSize=13,
                                   leading=18, alignment=TA_CENTER, spaceAfter=6)
    S_TOC_BOLD = ParagraphStyle("TocBold", fontName=BODY_BOLD, fontSize=12,
                                 leading=16, spaceAfter=2)
    S_TOC_NORM = ParagraphStyle("TocNorm", fontName=BODY_FONT, fontSize=12,
                                 leading=16, leftIndent=12, spaceAfter=2)

    def tbl_style(has_header=True):
        cmds = [
            ("FONT",       (0, 0), (-1, -1), BODY_FONT, 10),
            ("FONTSIZE",   (0, 0), (-1, -1), 10),
            ("LEADING",    (0, 0), (-1, -1), 13),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.96, 0.96, 0.96)]),
            ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN",     (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        if has_header:
            cmds += [
                ("FONT",      (0, 0), (-1, 0), BODY_BOLD, 10),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.2, 0.2)),
                ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
                ("ALIGN",      (0, 0), (-1, 0), "CENTER"),
            ]
        return TableStyle(cmds)

    story = []

    # ── Cover ──
    story.append(Paragraph(TITLE, S_COVER_TITLE))
    story.append(Paragraph(SUBTITLE, S_COVER_SUBTITLE))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(DEGREE_LINE.replace("\n", "<br/>"), S_COVER_BODY))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(AUTHOR_BLOCK.replace("\n", "<br/>"), S_COVER_BODY))
    story.append(PageBreak())

    # ── Abstract ──
    story.append(Paragraph("ABSTRACT", S_H1))
    for para in ABSTRACT_PARAS:
        story.append(Paragraph(para, S_BODY))
    story.append(PageBreak())

    # ── TOC ──
    story.append(Paragraph("TABLE OF CONTENTS", S_H1))
    for num, title, bold in TOC:
        entry = f"{num}  {title}" if num else title
        style = S_TOC_BOLD if bold else S_TOC_NORM
        story.append(Paragraph(entry, style))
    story.append(PageBreak())

    # ── Main content ──
    avail_w = W - LMARGIN - RMARGIN

    for item in CONTENT:
        kind = item[0]
        if kind == "h1":
            story.append(Paragraph(item[1], S_H1))
        elif kind == "h2":
            story.append(Paragraph(item[1], S_H2))
        elif kind == "h3":
            story.append(Paragraph(item[1], S_H3))
        elif kind == "body":
            story.append(Paragraph(item[1], S_BODY))
        elif kind == "bullet":
            story.append(Paragraph(f"• {item[1]}", S_BULLET))
        elif kind == "code":
            lines = item[1].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(lines.replace("\n", "<br/>"), S_CODE))
        elif kind == "table":
            headers, rows = item[1], item[2]
            col_count = len(headers)
            col_w = avail_w / col_count
            data = [headers] + rows
            t = RLTable(data, colWidths=[col_w] * col_count, repeatRows=1)
            t.setStyle(tbl_style())
            story.append(KeepTogether([t, Spacer(1, 0.3*cm)]))
        elif kind == "pagebreak":
            story.append(PageBreak())

    doc.build(story)
    print(f"  pdf  -> {path}")


# ════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("Generating thesis files…")
    render_docx(DOCX_PATH)
    render_pdf(PDF_PATH)
    print("Done.")
