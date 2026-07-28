"""
Baseline single-agent implementation.

Unlike the multi-agent architecture, this baseline performs the entire
SQL generation process using a single LLM call without any specialised
agent routing or self-correction.

It is used only for evaluation purposes.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.database.sql_engine import (
    get_schema,
    generate_sql,
)

from src.agents.safety import (
    validate_sql_readonly,
)

from src.config.settings import settings
from src.llm import build_llm


DB_PATH = settings.database_path
MAX_ROWS = 1000


def execute_query(sql: str, db_path: Path = DB_PATH) -> dict[str, Any]:

    sql = validate_sql_readonly(sql)

    uri = f"file:{db_path}?mode=ro"

    connection = sqlite3.connect(uri, uri=True)

    try:

        cursor = connection.execute(sql)

        columns = [d[0] for d in cursor.description]

        rows = cursor.fetchmany(MAX_ROWS)

    finally:

        connection.close()

    return {
        "columns": columns,
        "rows": [list(r) for r in rows],
        "sql": sql,
    }


def run_single_agent(question: str) -> dict[str, Any]:

    llm = build_llm()

    schema = get_schema()

    sql = generate_sql(
        question,
        schema,
        llm,
    )

    try:

        result = execute_query(sql)

        result.update(
            ok=True,
            attempts=1,
            retried=False,
            error=None,
        )

        return result

    except Exception as e:

        return {

            "ok": False,

            "columns": [],

            "rows": [],

            "sql": sql,

            "attempts": 1,

            "retried": False,

            "error": str(e),

        }