"""
DuckDB connector for the business assistant analytical layer.

Architecture note
-----------------
The project uses TWO databases with distinct roles:
  - DuckDB (this file)  — analytical engine for running SELECT queries over
                          business data. Stored in business_assistant.db.
                          Handles: user-uploaded CSVs + Athena tables loaded on demand.
  - PostgreSQL           — operational store for users, threads, messages,
                          glossary entries, and LangGraph checkpoints.

Every public function opens a fresh DuckDB connection via get_conn() and closes
it automatically via the context manager.  DuckDB is single-writer but supports
multiple readers, so this connection-per-call pattern is safe for the async
FastAPI server (each request runs in its own thread pool slot).

Table ownership
---------------
User-uploaded and Athena-loaded tables are prefixed with a sanitised user_id
fragment so they never collide across users.  The _dataset_ownership shadow table
tracks which user owns which table.  Athena-loaded tables additionally appear in
_dataset_athena_meta with provenance and refresh metadata.
"""
import io
import json
import logging
import re
from pathlib import Path

import duckdb
import pandas as pd

from app.core.config import settings


def _resolve_db_path() -> str:
    if settings.DUCKDB_PATH:
        return settings.DUCKDB_PATH
    # Anchor to backend/ regardless of where uvicorn is invoked from.
    # __file__ = backend/app/data/duckdb_connector.py → parents[2] = backend/
    return str(Path(__file__).resolve().parents[2] / "business_assistant.db")


_BUILTIN_TABLES: set[str] = set()
_SYSTEM_TABLES = {"_dataset_ownership", "_dataset_athena_meta", "_athena_direct_refs"}

_MAX_LOAD_ROWS = 500_000

logger = logging.getLogger(__name__)


def get_conn() -> duckdb.DuckDBPyConnection:
    """Open and return a new DuckDB connection to the persistent database file."""
    return duckdb.connect(_resolve_db_path())


def _ensure_ownership_table() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _dataset_ownership (
                table_name        VARCHAR PRIMARY KEY,
                user_id           VARCHAR NOT NULL,
                original_filename VARCHAR NOT NULL,
                uploaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _ensure_athena_meta_table() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _dataset_athena_meta (
                duckdb_table_name  VARCHAR PRIMARY KEY,
                user_id            VARCHAR NOT NULL,
                athena_database    VARCHAR NOT NULL,
                athena_table_name  VARCHAR NOT NULL,
                athena_cred_source VARCHAR NOT NULL,
                row_count          INTEGER NOT NULL DEFAULT 0,
                row_limit_applied  BOOLEAN NOT NULL DEFAULT FALSE,
                loaded_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _ensure_athena_direct_refs_table() -> None:
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _athena_direct_refs (
                ref_name           VARCHAR PRIMARY KEY,
                user_id            VARCHAR NOT NULL,
                athena_database    VARCHAR NOT NULL,
                athena_table       VARCHAR NOT NULL,
                athena_cred_source VARCHAR NOT NULL,
                schema_json        TEXT NOT NULL,
                registered_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)


def _athena_direct_name(database: str, table: str, user_id: str) -> str:
    """Generate a stable, user-scoped ref name for an Athena direct-query table."""
    sanitized_db = re.sub(r"[^\w]", "_", database).lower()
    sanitized_table = re.sub(r"[^\w]", "_", table).lower()
    combined = f"{sanitized_db}__{sanitized_table}"
    if combined and combined[0].isdigit():
        combined = "_" + combined
    user_prefix = re.sub(r"[^a-z0-9]", "", user_id.lower())[:8]
    return f"u{user_prefix}_d_{combined}"[:60]


def register_athena_direct(
    database: str,
    table: str,
    cred_source: str,
    user_id: str,
    schema: list[dict],
) -> dict:
    """Upsert an Athena table as a schema-only direct-query reference in DuckDB."""
    _ensure_athena_direct_refs_table()
    ref_name = _athena_direct_name(database, table, user_id)
    schema_json = json.dumps(schema)

    with get_conn() as conn:
        conn.execute("DELETE FROM _athena_direct_refs WHERE ref_name = ?", [ref_name])
        conn.execute(
            """INSERT INTO _athena_direct_refs
               (ref_name, user_id, athena_database, athena_table, athena_cred_source, schema_json, registered_at)
               VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            [ref_name, user_id, database, table, cred_source, schema_json],
        )

    logger.info(
        "[athena_direct] Registered %s.%s → %s (user=%s)", database, table, ref_name, user_id[:8]
    )
    return {
        "ref_name": ref_name,
        "athena_database": database,
        "athena_table": table,
        "athena_cred_source": cred_source,
        "columns": schema,
    }


def unregister_athena_direct(database: str, table: str, user_id: str) -> None:
    """Remove an Athena direct-query registration."""
    _ensure_athena_direct_refs_table()
    ref_name = _athena_direct_name(database, table, user_id)
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM _athena_direct_refs WHERE ref_name = ? AND user_id = ?",
            [ref_name, user_id],
        )
    logger.info("[athena_direct] Unregistered %s (user=%s)", ref_name, user_id[:8])


def get_athena_direct_refs(user_id: str) -> list[dict]:
    """Return all Athena direct-query registrations for this user."""
    _ensure_athena_direct_refs_table()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT ref_name, athena_database, athena_table, athena_cred_source,
                      schema_json, registered_at
               FROM _athena_direct_refs WHERE user_id = ?""",
            [user_id],
        ).fetchall()
    result = []
    for r in rows:
        try:
            columns = json.loads(r[4])
        except Exception:
            columns = []
        result.append({
            "ref_name": r[0],
            "athena_database": r[1],
            "athena_table": r[2],
            "athena_cred_source": r[3],
            "columns": columns,
            "registered_at": r[5].isoformat() if r[5] else None,
        })
    return result


def get_table_names() -> list[str]:
    """Return all DuckDB table names except internal system tables."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' ORDER BY table_name"
        ).fetchall()
        return [r[0] for r in rows if r[0] not in _SYSTEM_TABLES]


def get_table_schema(table_name: str) -> list[dict]:
    """Return [{column, type}, …] for every column in table_name."""
    with get_conn() as conn:
        rows = conn.execute(f"DESCRIBE {table_name}").fetchall()
        return [{"column": r[0], "type": r[1]} for r in rows]


def get_sample_rows(table_name: str, n: int = 3) -> list[dict]:
    """Return up to n rows from table_name as a list of dicts."""
    with get_conn() as conn:
        df = conn.execute(f"SELECT * FROM {table_name} LIMIT {n}").fetchdf()
        return df.to_dict(orient="records")


def describe_all_tables() -> dict[str, dict]:
    """Return schema+sample for ALL tables (used by eval scripts only)."""
    result = {}
    for name in get_table_names():
        result[name] = {
            "schema": get_table_schema(name),
            "sample": get_sample_rows(name),
        }
    return result


def describe_user_tables(user_id: str) -> dict[str, dict]:
    """Return schema+sample for this user's tables (CSV uploads + Athena loads + Athena direct refs)."""
    result = {}
    for name in get_user_table_names(user_id):
        try:
            result[name] = {
                "schema": get_table_schema(name),
                "sample": get_sample_rows(name),
            }
        except Exception:
            pass

    # Merge Athena direct refs (schema-only, no row data in DuckDB)
    for ref in get_athena_direct_refs(user_id):
        result[ref["ref_name"]] = {
            "schema": ref["columns"],
            "sample": [],
            "athena_direct": True,
            "athena_database": ref["athena_database"],
            "athena_table": ref["athena_table"],
            "athena_cred_source": ref["athena_cred_source"],
        }

    return result


def get_user_table_names(user_id: str) -> list[str]:
    """Return tables owned by this user (both CSV and Athena-loaded)."""
    _ensure_ownership_table()
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT table_name FROM _dataset_ownership WHERE user_id = ?", [user_id]
        ).fetchall()
    return [r[0] for r in rows]


def dry_run_query(sql: str) -> str | None:
    """
    Validate SQL by running EXPLAIN without executing it.
    Returns None if valid, or the error string if invalid.
    """
    with get_conn() as conn:
        try:
            conn.execute(f"EXPLAIN {sql}")
            return None
        except Exception as exc:
            return str(exc)


def execute_query(sql: str, timeout_seconds: int = 60) -> list[dict]:
    """Execute a SELECT query against DuckDB and return results as a list of dicts."""
    with get_conn() as conn:
        try:
            conn.execute(f"SET query_timeout={timeout_seconds * 1000}")
        except Exception:
            pass
        try:
            df = conn.execute(sql).fetchdf()
        except Exception as exc:
            msg = str(exc).lower()
            if "timeout" in msg or "interrupt" in msg or "cancelled" in msg:
                raise TimeoutError(f"Query cancelled after {timeout_seconds}s") from exc
            raise
        return df.to_dict(orient="records")


def execute_query_with_bridge(
    sql: str,
    bridge_tables: "dict[str, pd.DataFrame]",
    timeout_seconds: int = 60,
) -> list[dict]:
    """Execute a DuckDB query with extra DataFrames registered as temporary views."""
    with get_conn() as conn:
        for name, df in bridge_tables.items():
            conn.register(name, df)
        try:
            conn.execute(f"SET query_timeout={timeout_seconds * 1000}")
        except Exception:
            pass
        try:
            result_df = conn.execute(sql).fetchdf()
        except Exception as exc:
            msg = str(exc).lower()
            if "timeout" in msg or "interrupt" in msg or "cancelled" in msg:
                raise TimeoutError(f"Query cancelled after {timeout_seconds}s") from exc
            raise
        return result_df.to_dict(orient="records")


def _sanitize_table_name(filename: str, user_id: str) -> str:
    """Derive a safe, user-scoped DuckDB table name from filename + user_id."""
    stem = filename.rsplit(".", 1)[0]
    name = re.sub(r"[^\w]", "_", stem).lower()
    if name and name[0].isdigit():
        name = "_" + name
    user_prefix = re.sub(r"[^a-z0-9]", "", user_id.lower())[:8]
    return f"u{user_prefix}_{name}"[:60]


def _athena_duckdb_name(database: str, table: str, user_id: str) -> str:
    """Generate a stable, user-scoped DuckDB table name for an Athena table."""
    combined = re.sub(r"[^\w]", "_", f"{database}_{table}").lower()
    if combined and combined[0].isdigit():
        combined = "_" + combined
    user_prefix = re.sub(r"[^a-z0-9]", "", user_id.lower())[:8]
    return f"u{user_prefix}_{combined}"[:60]


def _next_versioned_name(base: str, user_id: str, conn) -> str:
    """Return base if unclaimed; otherwise base_v2, base_v3 … up to base_v99."""
    existing = {
        r[0] for r in conn.execute(
            "SELECT table_name FROM _dataset_ownership WHERE user_id = ?", [user_id]
        ).fetchall()
    }
    if base not in existing:
        return base
    for v in range(2, 100):
        candidate = f"{base[:55]}_v{v}"  # keep total ≤60
        if candidate not in existing:
            return candidate
    raise ValueError("Too many versions of this file (max 98). Please delete some old uploads.")


def ingest_csv(file_bytes: bytes, filename: str, user_id: str) -> dict:
    """Read CSV bytes into DuckDB as a new table owned by user_id.

    Uploading a file whose name matches an existing table creates a new versioned
    table (e.g. u1234_sales_v2) instead of overwriting the original.
    """
    _ensure_ownership_table()
    base_name = _sanitize_table_name(filename, user_id)
    df = pd.read_csv(io.BytesIO(file_bytes))
    if df.empty:
        raise ValueError("CSV file is empty")

    with get_conn() as conn:
        table_name = _next_versioned_name(base_name, user_id, conn)
        conn.register("_upload_df", df)
        conn.execute(f"CREATE TABLE {table_name} AS SELECT * FROM _upload_df")
        row_count = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        conn.execute(
            "INSERT INTO _dataset_ownership (table_name, user_id, original_filename) VALUES (?, ?, ?)",
            [table_name, user_id, filename],
        )

    logger.info("[datasets] Ingested %s → %s (%d rows) user=%s", filename, table_name, row_count, user_id)
    schema = get_table_schema(table_name)
    return {"table_name": table_name, "original_filename": filename, "row_count": row_count, "columns": schema}


def load_athena_table(
    rows: list[dict],
    database: str,
    table: str,
    cred_source: str,
    user_id: str,
    row_limit_applied: bool = False,
) -> dict:
    """
    Load Athena query results into DuckDB as a persistent user-owned table.

    Uses pandas as the intermediary so all Athena types (varchar, bigint, double,
    date, timestamp, array/map serialised as strings) are cast gracefully by
    pandas inference before landing in DuckDB.
    """
    _ensure_ownership_table()
    _ensure_athena_meta_table()

    duckdb_name = _athena_duckdb_name(database, table, user_id)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("Athena table returned no rows")

    # Coerce obvious date/timestamp columns
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().head(5).tolist()
            if sample and all(isinstance(v, str) and len(v) >= 10 and v[4] == "-" for v in sample):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass

    with get_conn() as conn:
        conn.register("_athena_load_df", df)
        conn.execute(f"CREATE OR REPLACE TABLE {duckdb_name} AS SELECT * FROM _athena_load_df")
        row_count = conn.execute(f"SELECT COUNT(*) FROM {duckdb_name}").fetchone()[0]

        conn.execute("DELETE FROM _dataset_ownership WHERE table_name = ?", [duckdb_name])
        conn.execute(
            "INSERT INTO _dataset_ownership (table_name, user_id, original_filename) VALUES (?, ?, ?)",
            [duckdb_name, user_id, f"__athena__{database}__{table}"],
        )

        conn.execute("DELETE FROM _dataset_athena_meta WHERE duckdb_table_name = ?", [duckdb_name])
        conn.execute(
            """INSERT INTO _dataset_athena_meta
               (duckdb_table_name, user_id, athena_database, athena_table_name,
                athena_cred_source, row_count, row_limit_applied, loaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
            [duckdb_name, user_id, database, table, cred_source, row_count, row_limit_applied],
        )

    logger.info(
        "[athena] Loaded %s.%s → %s (%d rows, capped=%s) user=%s",
        database, table, duckdb_name, row_count, row_limit_applied, user_id[:8],
    )
    schema = get_table_schema(duckdb_name)
    return {
        "table_name": duckdb_name,
        "athena_database": database,
        "athena_table_name": table,
        "row_count": row_count,
        "row_limit_applied": row_limit_applied,
        "columns": schema,
    }


def get_athena_loaded_tables(user_id: str) -> list[dict]:
    """Return metadata for Athena tables loaded into DuckDB by this user."""
    _ensure_athena_meta_table()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT duckdb_table_name, athena_database, athena_table_name,
                      athena_cred_source, row_count, row_limit_applied, loaded_at
               FROM _dataset_athena_meta WHERE user_id = ?""",
            [user_id],
        ).fetchall()
    return [
        {
            "duckdb_table_name": r[0],
            "athena_database": r[1],
            "athena_table_name": r[2],
            "athena_cred_source": r[3],
            "row_count": r[4],
            "row_limit_applied": bool(r[5]),
            "loaded_at": r[6].isoformat() if r[6] else None,
        }
        for r in rows
    ]


def drop_uploaded_table(table_name: str, user_id: str) -> None:
    """Drop a user table (CSV or Athena-loaded) after verifying ownership."""
    _ensure_ownership_table()
    _ensure_athena_meta_table()
    if table_name in _BUILTIN_TABLES:
        raise ValueError(f"Cannot delete built-in table '{table_name}'")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT user_id FROM _dataset_ownership WHERE table_name = ?", [table_name]
        ).fetchone()
        if row is None:
            raise ValueError(f"Table '{table_name}' not found")
        if row[0] != user_id:
            raise PermissionError(f"Table '{table_name}' belongs to another user")
        conn.execute(f"DROP TABLE IF EXISTS {table_name}")
        conn.execute("DELETE FROM _dataset_ownership WHERE table_name = ?", [table_name])
        conn.execute("DELETE FROM _dataset_athena_meta WHERE duckdb_table_name = ?", [table_name])

    logger.info("[datasets] Dropped table %s (user=%s)", table_name, user_id)


def list_uploaded_tables(user_id: str) -> list[dict]:
    """Return metadata for all tables owned by this user, with Athena provenance where applicable."""
    _ensure_ownership_table()
    _ensure_athena_meta_table()

    with get_conn() as conn:
        ownership_rows = conn.execute(
            "SELECT table_name FROM _dataset_ownership WHERE user_id = ?", [user_id]
        ).fetchall()
        athena_rows = conn.execute(
            """SELECT duckdb_table_name, athena_database, athena_table_name,
                      athena_cred_source, row_count, row_limit_applied, loaded_at
               FROM _dataset_athena_meta WHERE user_id = ?""",
            [user_id],
        ).fetchall()

    athena_meta: dict[str, dict] = {
        r[0]: {
            "athena_database": r[1],
            "athena_table_name": r[2],
            "athena_cred_source": r[3],
            "row_count": r[4],
            "row_limit_applied": bool(r[5]),
            "loaded_at": r[6].isoformat() if r[6] else None,
        }
        for r in athena_rows
    }

    result = []
    for (name,) in ownership_rows:
        try:
            count = execute_query(f"SELECT COUNT(*) AS cnt FROM {name}")[0]["cnt"]
            entry: dict = {
                "table_name": name,
                "row_count": count,
                "columns": get_table_schema(name),
                "source_type": "csv",
            }
            if name in athena_meta:
                entry.update(athena_meta[name])
                entry["source_type"] = "athena"
                entry["row_count"] = count  # live DuckDB count overrides stored count
            result.append(entry)
        except Exception:
            pass

    # Append Athena direct refs
    for ref in get_athena_direct_refs(user_id):
        result.append({
            "table_name": ref["ref_name"],
            "source_type": "athena_direct",
            "row_count": 0,
            "columns": ref["columns"],
            "athena_database": ref["athena_database"],
            "athena_table": ref["athena_table"],
            "athena_cred_source": ref["athena_cred_source"],
            "registered_at": ref["registered_at"],
        })

    return result
