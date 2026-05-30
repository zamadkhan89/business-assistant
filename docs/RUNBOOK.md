# Runbook — Starting, Using, and Stopping the Business Assistant

Quick operational reference. For architecture details see ARCHITECTURE.md; for the demo sequence see DEMO_SCRIPT.md.

---

## One-Command Start / Stop

From the project root (`d:\business-assistant`):

```powershell
.\dev.ps1           # start both backend + frontend (default)
.\dev.ps1 start     # same as above
.\dev.ps1 stop      # stop both
.\dev.ps1 restart   # stop then start
.\dev.ps1 status    # show what is running + health check
```

Each service opens in its own PowerShell window so you can see the logs.
Wait for both windows to print their "ready" message before opening the browser.

---

## Prerequisites — Check These Once

```powershell
# 1. Python venv exists
Test-Path d:\business-assistant\backend\.venv   # must be True

# 2. Node modules installed
Test-Path d:\business-assistant\frontend\node_modules   # must be True

# 3. PostgreSQL 16 is running
pg_isready -U postgres -p 5432                 # must print "accepting connections"

# 4. .env file exists and has required keys
Get-Content d:\business-assistant\backend\.env | Select-String "GOOGLE_API_KEY|SECRET_KEY|DATABASE_URL"
# Must show all three lines with non-empty values
```

If PostgreSQL is not running, start it:
```powershell
Start-Service postgresql-x64-16    # service name may vary — check Services app
```

---

## Starting the System

Open **two separate PowerShell terminals** — one for the backend, one for the frontend.

### Terminal 1 — Backend

```powershell
cd d:\business-assistant\backend
.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Wait for these lines** before touching the frontend:
```
INFO:     Started server process
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

You may also see ChromaDB downloading its embedding model on first run (~79 MB). That is normal — it is cached after the first download.

### Terminal 2 — Frontend

```powershell
cd d:\business-assistant\frontend
npm run dev
```

**Wait for:**
```
▲ Next.js 16.x.x
- Local:   http://localhost:3001
```

**Open the app:** http://localhost:3001

---

## What to Check After Starting

### Quick health check (backend)

```powershell
Invoke-RestMethod http://localhost:8000/health
# Expected: { "status": "ok" }
```

### Verify backend is wired to the LLM

```powershell
Invoke-RestMethod http://localhost:8000/health
```

If the backend crashed (e.g. missing API key), `uvicorn` will show a traceback in Terminal 1. Fix it, then restart.

### Verify the database

```powershell
psql -U postgres -d business_assistant -c "\dt"
# Must list: users, threads, messages, glossary_entries, saved_queries, alembic_version
```

### Verify tests still pass (run before demo, not during)

```powershell
cd d:\business-assistant\backend
python -m pytest --tb=short -q
# Must print: 75 passed
```

---

## Using the System — Walkthrough

### Sign up / Log in

1. Go to http://localhost:3001
2. You will be redirected to `/login`. Click **Sign up** if you have no account.
3. Enter any email + password (minimum 8 characters). The system creates a local account.
4. After login, you land on `/chat`.

### Ask a data question

Type any question about the built-in Northwind sample data, for example:
- `Who are the top 5 customers by revenue?`
- `How many orders did we get each month?`
- `Which product has the highest total sales?`

The pipeline runs: Supervisor → Schema Agent → SQL Agent → **approval panel**.

### Human-in-the-loop approval panel

When the amber panel appears:
- Read the plain-English explanation of what the SQL does.
- Click **View SQL** to see the raw query.
- **Approve** — runs as-is. A chart appears below the message.
- **Edit SQL** — a text area opens. Change the SQL, click **Approve with edits**.
- **Reject** — discards the query; type a rephrased question to try again.

### Upload a CSV

1. Click **Upload CSV** in the chat sidebar header.
2. Select any `.csv` file (max 10 MB).
3. The new table name appears in the sidebar.
4. Ask questions about it: `Show me the top 10 rows from my uploaded data`

### Manage the business glossary

1. Click **Glossary** in the chat sidebar footer.
2. Add a term, e.g. `revenue` = `quantity times unit_price`.
3. Go back to chat and ask a question using that term — the SQL agent will apply your definition.

### View past conversations

Click any thread in the left sidebar to reload a previous conversation. The full message history is restored from PostgreSQL.

### Download results as CSV

After a chart appears, click **Download as CSV** below the chart to export the query result.

### Dark/light mode

Click the moon/sun toggle at the bottom of the sidebar.

---

## Stopping the System

### Stop the backend
In Terminal 1: press `Ctrl + C`.

### Stop the frontend
In Terminal 2: press `Ctrl + C`.

### Stop PostgreSQL (optional — only if you want to fully shut down)
```powershell
Stop-Service postgresql-x64-16
```

You do not need to stop PostgreSQL between sessions. Leaving it running is fine.

---

## Common Problems and Fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `/health` returns connection refused | Backend not started | Check Terminal 1 for errors; restart uvicorn |
| `pg_isready` fails | PostgreSQL not running | `Start-Service postgresql-x64-16` |
| Chat sends request but nothing comes back | LLM API key missing or quota exceeded | Check `GOOGLE_API_KEY` in `backend/.env`; check Google AI Studio quota |
| ChromaDB hangs on startup | First-run model download | Wait — the 79 MB ONNX model downloads once and is cached |
| `401 Unauthorized` in browser | Session expired or not logged in | Refresh `/login` and sign in again |
| SQL panel never appears | Supervisor classified as off-topic or greetings | Rephrase as a data question: "show me total revenue" |
| Chart does not render | Plotly JS not loaded | Hard-refresh the page (`Ctrl + Shift + R`) |
| `75 passed` drops below 75 | A code change broke something | Run `python -m pytest --tb=long` to see which test failed |
| `NEXT_PUBLIC_BACKEND_URL` not set | Frontend can't reach backend | Add to `frontend/.env.local`: `NEXT_PUBLIC_BACKEND_URL=http://localhost:8000` |

---

## Environment Variables Reference

All backend vars live in `backend/.env`. The file is gitignored — never commit it.

| Variable | Required | Example value | Purpose |
|---|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+asyncpg://postgres:postgres@localhost:5432/business_assistant` | SQLAlchemy (async) connection to PostgreSQL |
| `POSTGRES_URL` | Yes | `postgresql://postgres:postgres@localhost:5432/business_assistant` | LangGraph checkpointer connection (sync psycopg) |
| `SECRET_KEY` | Yes | any long random string | Signs and verifies JWTs |
| `GOOGLE_API_KEY` | Yes* | `AIza...` | Gemini API key (`*` swap for other provider) |
| `LLM_PROVIDER` | No | `google_genai` | Provider: `google_genai` / `anthropic` / `openai` |
| `LLM_MODEL` | No | `gemini-2.0-flash` | Model name for the chosen provider |
| `QUERY_TIMEOUT_SECONDS` | No | `60` | Max DuckDB query runtime before TimeoutError |

To switch to Anthropic Claude:
```
LLM_PROVIDER=anthropic
LLM_MODEL=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

---

## File Locations

| What | Where |
|---|---|
| Backend source | `d:\business-assistant\backend\app\` |
| Backend tests | `d:\business-assistant\backend\tests\` |
| DuckDB data file | `d:\business-assistant\backend\business_assistant.db` |
| Backend .env | `d:\business-assistant\backend\.env` |
| Frontend source | `d:\business-assistant\frontend\app\` |
| Frontend .env | `d:\business-assistant\frontend\.env.local` (create if missing) |
| Logs | Printed to the terminal running uvicorn — no log files by default |

---

## Restart Checklist (for defense day)

```powershell
# Run in order:
pg_isready -U postgres -p 5432          # must print "accepting connections"
.\dev.ps1 start                          # opens backend + frontend windows
# wait ~10 seconds, then:
.\dev.ps1 status                         # must show both RUNNING + "Health check: ok"
```

```
[ ] PostgreSQL running          pg_isready prints "accepting connections"
[ ] Both services running       .\dev.ps1 status shows RUNNING for both
[ ] Health check passes         status shows "Health check: ok"
[ ] Browser open at             http://localhost:3001  (already logged in)
[ ] Test account ready          know the email+password you signed up with
[ ] Sample question ready       typed and waiting — just press Enter when panel looks at you
```
