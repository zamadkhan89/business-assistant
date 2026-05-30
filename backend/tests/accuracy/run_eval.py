"""
Accuracy evaluation harness for the business assistant SQL agent.

Usage (from backend/ directory with venv active):
    python tests/accuracy/run_eval.py
    python tests/accuracy/run_eval.py --model gemini-1.5-flash-8b
    python tests/accuracy/run_eval.py --provider anthropic --model claude-haiku-4-5-20251001
    python tests/accuracy/run_eval.py --delay 5   # seconds between questions

Requires the matching API key in backend/.env.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Allow running from backend/ directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv  # noqa: E402
_env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(_env_path)

from app.data.sample_data import load_sample_data          # noqa: E402
from app.data.duckdb_connector import describe_all_tables, execute_query  # noqa: E402
from app.agents.sql_agent import generate_sql, validate_sql  # noqa: E402
from tests.accuracy.fixtures import QUESTIONS              # noqa: E402

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

_MAX_RETRIES = 3
_RETRY_BACKOFF = [10, 30, 60]   # seconds between retries


def _generate_with_retry(question: str, schema: dict, retries: int = _MAX_RETRIES) -> str:
    """Call generate_sql with exponential backoff on 429 / rate-limit errors."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return generate_sql(question, schema)
        except Exception as exc:
            msg = str(exc)
            is_quota = "RESOURCE_EXHAUSTED" in msg or "429" in msg or "rate" in msg.lower()
            if is_quota and attempt < retries:
                wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                print(f"       {YELLOW}[rate limit] retrying in {wait}s (attempt {attempt+1}/{retries})...{RESET}")
                time.sleep(wait)
                last_exc = exc
                continue
            raise exc from last_exc


def run_eval(delay: float = 2.0, verbose: bool = True) -> dict:
    load_sample_data()
    schema = describe_all_tables()

    results = []

    print(f"\n{BOLD}Business Assistant - Accuracy Evaluation{RESET}")
    print("-" * 60)
    print(f"  Questions : {len(QUESTIONS)}")
    print(f"  LLM       : {os.getenv('LLM_PROVIDER','?')}/{os.getenv('LLM_MODEL','?')}")
    print(f"  Delay     : {delay}s between questions")
    print("-" * 60 + "\n")

    for idx, q in enumerate(QUESTIONS):
        if idx > 0:
            time.sleep(delay)

        qid      = q["id"]
        question = q["question"]
        expected = q["expected"]
        check    = q["check"]

        t0     = time.time()
        status = "PASS"
        sql    = ""
        rows: list[dict] = []
        error  = ""

        try:
            sql = _generate_with_retry(question, schema)
        except Exception as exc:
            status = "FAIL"
            error  = f"generate_sql error: {str(exc)[:120]}"

        if status == "PASS":
            is_valid, val_err = validate_sql(sql)
            if not is_valid:
                status = "FAIL"
                error  = f"SQL invalid: {val_err}"

        if status == "PASS":
            try:
                rows = execute_query(sql)
            except Exception as exc:
                status = "FAIL"
                error  = f"execute error: {exc}"

        if status == "PASS":
            try:
                passed = check(rows)
            except Exception as exc:
                passed = False
                error  = f"check error: {exc}"
            status = "PASS" if passed else "FAIL"
            if not passed and not error:
                first_val = list(rows[0].values())[0] if rows else "<empty>"
                error = f"got {first_val!r}, expected ~{expected!r}"

        elapsed = time.time() - t0
        colour  = GREEN if status == "PASS" else RED
        label   = f"{colour}[{status}]{RESET}"

        print(f"{label} {qid}: {question}")
        if verbose and sql:
            sql_short = sql.replace("\n", " ")
            sql_short = sql_short if len(sql_short) <= 110 else sql_short[:110] + "..."
            print(f"       SQL : {sql_short}")
        if status == "FAIL":
            print(f"       {YELLOW}-> {error}{RESET}")
        print(f"       {elapsed:.1f}s\n")

        results.append({
            "id": qid, "question": question, "status": status,
            "sql": sql, "rows": rows, "error": error, "elapsed": elapsed,
        })

    passed = sum(1 for r in results if r["status"] == "PASS")
    total  = len(results)
    pct    = 100 * passed // total

    colour = GREEN if pct >= 80 else (YELLOW if pct >= 60 else RED)
    print("=" * 60)
    print(f"{BOLD}Result: {colour}{passed}/{total} correct ({pct}%){RESET}")
    print("=" * 60 + "\n")

    fails = [r for r in results if r["status"] == "FAIL"]
    if fails:
        print(f"{BOLD}Failed questions:{RESET}")
        for r in fails:
            print(f"  * {r['id']}: {r['question']}")
            print(f"    {YELLOW}{r['error']}{RESET}")
        print()

    return {"passed": passed, "total": total, "pct": pct, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run accuracy evaluation")
    parser.add_argument("--provider", help="Override LLM_PROVIDER env var")
    parser.add_argument("--model",    help="Override LLM_MODEL env var")
    parser.add_argument("--delay",    type=float, default=2.0,
                        help="Seconds to wait between questions (default 2)")
    args = parser.parse_args()

    if args.provider:
        os.environ["LLM_PROVIDER"] = args.provider
    if args.model:
        os.environ["LLM_MODEL"] = args.model

    run_eval(delay=args.delay, verbose=True)
