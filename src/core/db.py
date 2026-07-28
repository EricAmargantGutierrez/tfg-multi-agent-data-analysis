"""
src/core/db.py

The single place in the codebase that opens a connection to the SQLite
database. Every agent that needs data (SQL, Viz, Analysis) goes through
this module instead of calling sqlite3.connect() itself.

Why this exists (architecture decision, see docs/architecture.md):
    Three agents legitimately need independent read access to the data
    (each writes its own SQL rather than chaining through the orchestrator).
    That's a deliberate deviation from the original proposal, but it must
    not mean three different, possibly-inconsistent ways of opening the
    database. Centralizing here means:
      - every read is opened via the read-only URI (file:...?mode=ro), so
        a bug anywhere downstream cannot mutate the database;
      - schema introspection and column validation are defined once;
      - the row cap and read-only SQL guard are applied uniformly.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from src.agents.safety import validate_sql_readonly
from src.config.settings import settings

DB_PATH: Path = settings.database_path
MAX_ROWS = 1000

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _ro_uri(db_path: Path) -> str:
    return f"file:{db_path}?mode=ro"


def _connect_readonly(db_path: Path = DB_PATH) -> sqlite3.Connection:
    return sqlite3.connect(_ro_uri(db_path), uri=True)


# ---------------------------------------------------------------------
# Schema introspection
# ---------------------------------------------------------------------
def get_schema(db_path: Path = DB_PATH, table: str = "orders") -> str:
    """Human-readable schema description, used in LLM prompts."""
    if not _IDENTIFIER_RE.match(table):
        raise ValueError(f"Invalid table name '{table}'.")

    con = _connect_readonly(db_path)
    try:
        cols = con.execute(f"PRAGMA table_info({table})").fetchall()
        sample = con.execute(f"SELECT * FROM {table} LIMIT 2").fetchall()
    finally:
        con.close()

    lines = [f"Table: {table}", "Columns:"]
    for _, name, ctype, *_ in cols:
        lines.append(f"  - {name} ({ctype})")
    lines.append("")
    lines.append("Notes for writing SQL:")
    lines.append("  - order_date and ship_date are ISO strings 'YYYY-MM-DD'.")
    lines.append("  - Use strftime('%Y', order_date) to extract the year,")
    lines.append("    strftime('%Y-%m', order_date) for year-month.")
    lines.append(f"Sample rows: {sample}")
    return "\n".join(lines)


def get_valid_columns(db_path: Path = DB_PATH, table: str = "orders") -> set[str]:
    """Real column names pulled from SQLite, so LLM output can be checked
    against ground truth instead of trusted blindly."""
    if not _IDENTIFIER_RE.match(table):
        raise ValueError(f"Invalid table name '{table}'.")

    con = _connect_readonly(db_path)
    try:
        cursor = con.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}
    finally:
        con.close()


# ---------------------------------------------------------------------
# For SQL / Viz agents: the LLM writes complete, free-form SQL text.
# ---------------------------------------------------------------------
def run_readonly_query(sql: str, db_path: Path = DB_PATH) -> dict[str, Any]:
    """Validate + execute a full LLM-authored SQL string. Read-only, capped."""
    safe = validate_sql_readonly(sql)
    con = _connect_readonly(db_path)
    try:
        cur = con.execute(safe)
        columns = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchmany(MAX_ROWS)
    finally:
        con.close()
    return {"columns": columns, "rows": [list(r) for r in rows], "sql": safe}


def run_readonly_query_dicts(sql: str, db_path: Path = DB_PATH) -> list[dict]:
    """Same as run_readonly_query but returns list[dict] (used by the
    Viz agent, which needs named access to plot x/y columns)."""
    safe = validate_sql_readonly(sql)
    con = _connect_readonly(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(safe).fetchmany(MAX_ROWS)
    finally:
        con.close()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# For the Analysis agent: we build the SELECT ourselves from a validated
# plan (columns + filters), so we can safely parameter-bind filter values
# instead of ever string-interpolating LLM output into SQL.
# ---------------------------------------------------------------------
def build_select(
    columns: list[str],
    filters: list[dict] | None = None,
    table: str = "orders",
    valid_columns: set[str] | None = None,
) -> tuple[str, list]:
    """
    Build a parameterized SELECT from validated column names + filters.

    filters: list of {"column": str, "op": str, "value": Any}
      op is one of: = != > >= < <= LIKE IN BETWEEN
      IN expects a non-empty list value; BETWEEN expects a 2-element list.

    Returns (sql, params) where params are bound with '?' placeholders --
    filter VALUES are never interpolated into the SQL string.
    """
    if not _IDENTIFIER_RE.match(table):
        raise ValueError(f"Invalid table name '{table}'.")
    if not columns:
        raise ValueError("At least one column is required.")

    valid_columns = valid_columns if valid_columns is not None else get_valid_columns(table=table)

    bad_columns = [c for c in columns if c not in valid_columns]
    if bad_columns:
        raise ValueError(f"Unknown column(s): {bad_columns}. Valid columns: {sorted(valid_columns)}")

    sql = f"SELECT {', '.join(columns)} FROM {table}"
    params: list = []

    filters = filters or []
    if filters:
        clauses = []
        for f in filters:
            col, op, value = f["column"], f["op"], f["value"]

            if col not in valid_columns:
                raise ValueError(f"Unknown filter column '{col}'. Valid columns: {sorted(valid_columns)}")

            if op == "IN":
                if not isinstance(value, list) or not value:
                    raise ValueError(f"Filter on '{col}' with op IN requires a non-empty list value.")
                placeholders = ", ".join(["?"] * len(value))
                clauses.append(f"{col} IN ({placeholders})")
                params.extend(value)

            elif op == "BETWEEN":
                if not isinstance(value, list) or len(value) != 2:
                    raise ValueError(f"Filter on '{col}' with op BETWEEN requires a 2-element list value.")
                clauses.append(f"{col} BETWEEN ? AND ?")
                params.extend(value)

            elif op in ("=", "!=", ">", ">=", "<", "<=", "LIKE"):
                clauses.append(f"{col} {op} ?")
                params.append(value)

            else:
                raise ValueError(f"Unsupported filter operator '{op}'.")

        sql += " WHERE " + " AND ".join(clauses)

    return sql, params


def load_dataframe_readonly(sql: str, params: list | None = None, db_path: Path = DB_PATH) -> pd.DataFrame:
    """Run a self-built (not LLM-free-form) SELECT and return a DataFrame."""
    con = _connect_readonly(db_path)
    try:
        df = pd.read_sql_query(sql, con, params=params or [])
    finally:
        con.close()

    if df.empty:
        raise ValueError("The query returned no rows.")
    return df
