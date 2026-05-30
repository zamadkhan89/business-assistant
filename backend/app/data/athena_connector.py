"""
AWS Athena / Glue connector.

Uses boto3 for Glue Data Catalog browsing and boto3's Athena client for
query execution.  Requires:
  AWS_REGION, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY in .env
  ATHENA_WORKGROUP and ATHENA_OUTPUT_BUCKET for running queries.

All functions raise AthenaNotConfiguredError when credentials are absent,
so the API layer can return a helpful 503 instead of a crash.
"""
from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class AthenaNotConfiguredError(Exception):
    """Raised when AWS credentials / Athena settings are missing."""


def _get_clients(creds: dict | None = None):
    """
    Return (glue_client, athena_client).

    creds — optional dict with keys: aws_region, aws_access_key_id,
    aws_secret_access_key. When provided, these override the env-var defaults.
    """
    from app.core.config import settings  # local import to avoid circular at module load

    region     = (creds or {}).get("aws_region")     or settings.AWS_REGION
    key_id     = (creds or {}).get("aws_access_key_id")     or settings.AWS_ACCESS_KEY_ID
    secret_key = (creds or {}).get("aws_secret_access_key") or settings.AWS_SECRET_ACCESS_KEY

    if not key_id or not secret_key:
        raise AthenaNotConfiguredError(
            "AWS credentials not configured. Enter them on the Athena page or "
            "set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in backend/.env"
        )

    try:
        import boto3  # noqa: PLC0415
    except ImportError:
        raise AthenaNotConfiguredError("boto3 is not installed. Run: pip install boto3")

    session = boto3.Session(
        region_name=region,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret_key,
    )
    return session.client("glue"), session.client("athena")


# ── Glue Catalog ──────────────────────────────────────────────────────────────

def list_databases(creds: dict | None = None) -> list[dict]:
    """Return all Glue databases: [{name, description}]."""
    glue, _ = _get_clients(creds)
    dbs = []
    paginator = glue.get_paginator("get_databases")
    for page in paginator.paginate():
        for db in page.get("DatabaseList", []):
            dbs.append({
                "name": db["Name"],
                "description": db.get("Description", ""),
            })
    return dbs


def list_tables(database: str, creds: dict | None = None) -> list[dict]:
    """Return tables in a Glue database: [{name, description, columns}]."""
    glue, _ = _get_clients(creds)
    tables = []
    paginator = glue.get_paginator("get_tables")
    for page in paginator.paginate(DatabaseName=database):
        for tbl in page.get("TableList", []):
            storage = tbl.get("StorageDescriptor", {})
            columns = [
                {
                    "name": c["Name"],
                    "type": c["Type"],
                    "comment": c.get("Comment", ""),
                }
                for c in storage.get("Columns", [])
            ]
            # Partition keys
            for pk in tbl.get("PartitionKeys", []):
                columns.append({
                    "name": pk["Name"],
                    "type": pk["Type"],
                    "comment": pk.get("Comment", "") + " [partition key]",
                })
            tables.append({
                "name": tbl["Name"],
                "database": database,
                "description": tbl.get("Description", ""),
                "location": storage.get("Location", ""),
                "columns": columns,
                "row_count": None,  # Glue doesn't always have stats
            })
    return tables


def get_table_schema(database: str, table: str, creds: dict | None = None) -> dict:
    """Return schema + partition info for a single Glue table."""
    glue, _ = _get_clients(creds)
    resp = glue.get_table(DatabaseName=database, Name=table)
    tbl = resp["Table"]
    storage = tbl.get("StorageDescriptor", {})
    columns = [
        {"name": c["Name"], "type": c["Type"], "comment": c.get("Comment", "")}
        for c in storage.get("Columns", [])
    ]
    for pk in tbl.get("PartitionKeys", []):
        columns.append({
            "name": pk["Name"],
            "type": pk["Type"],
            "comment": pk.get("Comment", "") + " [partition key]",
        })
    return {
        "database": database,
        "table": table,
        "description": tbl.get("Description", ""),
        "location": storage.get("Location", ""),
        "columns": columns,
    }


# ── Athena Query Execution ────────────────────────────────────────────────────

def run_query(sql: str, database: str, timeout_seconds: int = 120, creds: dict | None = None) -> list[dict]:
    """
    Execute a SQL query via Athena and return results as a list of dicts.

    Polls until the query completes or timeout_seconds elapses.
    ATHENA_OUTPUT_BUCKET must be configured (via creds dict or env var).
    """
    from app.core.config import settings

    workgroup     = (creds or {}).get("athena_workgroup")     or settings.ATHENA_WORKGROUP
    output_bucket = (creds or {}).get("athena_output_bucket") or settings.ATHENA_OUTPUT_BUCKET

    if not output_bucket:
        raise AthenaNotConfiguredError(
            "Athena output bucket is not set. Enter it in the Athena settings or "
            "set ATHENA_OUTPUT_BUCKET in backend/.env (e.g. s3://my-bucket/results/)"
        )

    _, athena = _get_clients(creds)

    start_resp = athena.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": database},
        WorkGroup=workgroup,
        ResultConfiguration={"OutputLocation": output_bucket},
    )
    execution_id = start_resp["QueryExecutionId"]
    logger.info("[athena] Started query %s", execution_id)

    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status_resp = athena.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp["QueryExecution"]["Status"]["State"]

        if state == "SUCCEEDED":
            break
        if state in ("FAILED", "CANCELLED"):
            reason = status_resp["QueryExecution"]["Status"].get("StateChangeReason", state)
            raise RuntimeError(f"Athena query {state}: {reason}")
        time.sleep(1)
    else:
        athena.stop_query_execution(QueryExecutionId=execution_id)
        raise TimeoutError(f"Athena query timed out after {timeout_seconds}s")

    # Fetch results (paginated, max 1000 rows per page)
    rows = []
    headers: list[str] = []
    paginator = athena.get_paginator("get_query_results")
    first_page = True
    for page in paginator.paginate(QueryExecutionId=execution_id):
        result_rows = page["ResultSet"]["Rows"]
        if first_page:
            headers = [c["VarCharValue"] for c in result_rows[0]["Data"]]
            result_rows = result_rows[1:]
            first_page = False
        for row in result_rows:
            values = [cell.get("VarCharValue", "") for cell in row["Data"]]
            rows.append(dict(zip(headers, values)))
        if len(rows) >= 5000:
            logger.warning("[athena] Truncated results at 5000 rows")
            break

    logger.info("[athena] Query %s returned %d rows", execution_id, len(rows))
    return rows


def preview_table(database: str, table: str, limit: int = 50, creds: dict | None = None) -> list[dict]:
    """Run a simple SELECT * LIMIT query against an Athena table."""
    sql = f'SELECT * FROM "{database}"."{table}" LIMIT {limit}'
    return run_query(sql, database, creds=creds)
