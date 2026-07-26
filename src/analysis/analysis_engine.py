"""
analysis_engine.py

Core engine used by the Analysis Agent.

Pipeline:

Question
    ↓
Planner (LLM)
    ↓
Analysis plan
    ↓
SQLite
    ↓
pandas DataFrame
    ↓
statistics.py
    ↓
Structured result
"""

from __future__ import annotations

import json
import re
import sqlite3

import pandas as pd

from src.config.settings import settings
from src.database.sql_engine import get_schema
from src.llm import build_llm
from src.analysis.statistics import ANALYSIS_FUNCTIONS


SYSTEM_PROMPT = """
You are a planning assistant.

Your job is NOT to generate SQL.

Your task is to determine:

1. Which statistical analysis should be performed.
2. Which database columns are required.

Available analyses:

- describe
- count
- mean
- median
- mode
- min
- max
- variance
- std
- correlation
- covariance
- ttest
- regression
- pca
- kmeans

Return ONLY valid JSON.

Examples:

{
    "analysis":"mean",
    "columns":["sales"]
}

{
    "analysis":"correlation",
    "columns":["discount","profit"]
}

{
    "analysis":"regression",
    "columns":["sales","profit"]
}

Never generate SQL.
Never explain anything.
"""

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# ---------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------

def plan_analysis(
    question: str,
    llm,
    error_context: str | None = None,
) -> dict:

    user_prompt = f"""
Database schema:

{get_schema()}

Question:

{question}
"""

    if error_context:

        user_prompt += f"""

Previous attempt failed.

Error:

{error_context}

Return corrected JSON.
"""

    response = llm.invoke(
        [
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": user_prompt,
            },
        ]
    )

    raw = response.content.strip()

    raw = raw.replace("```json", "")
    raw = raw.replace("```", "")

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Planner did not return valid JSON: {exc}") from exc

    if not isinstance(plan, dict):
        raise ValueError("Planner response must be a JSON object.")

    if "analysis" not in plan or "columns" not in plan:
        raise ValueError("Planner response missing 'analysis' or 'columns'.")

    if not isinstance(plan["columns"], list) or not plan["columns"]:
        raise ValueError("Planner 'columns' must be a non-empty list.")

    if plan["analysis"] not in ANALYSIS_FUNCTIONS:
        raise ValueError(
            f"Unknown analysis '{plan['analysis']}'."
        )

    return plan


# ---------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------

def get_valid_columns(table: str = "orders") -> set[str]:
    """
    Fetch the real column names for `table` directly from SQLite,
    so planner output can be validated instead of trusted blindly.
    """

    if not _IDENTIFIER_RE.match(table):
        raise ValueError(f"Invalid table name '{table}'.")

    connection = sqlite3.connect(settings.database_path)

    try:
        cursor = connection.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cursor.fetchall()}

    finally:
        connection.close()


# ---------------------------------------------------------------------
# SQL Builder
# ---------------------------------------------------------------------

def build_sql(plan: dict, table: str = "orders") -> str:

    columns = plan["columns"]

    if not columns:
        raise ValueError("Planner returned no columns.")

    columns = [c.lower().replace(" ", "_") for c in columns]
    plan["columns"] = columns

    valid_columns = get_valid_columns(table)

    bad_columns = [c for c in columns if c not in valid_columns]

    if bad_columns:
        raise ValueError(
            f"Planner returned unknown column(s): {bad_columns}. "
            f"Valid columns are: {sorted(valid_columns)}"
        )

    # Columns are now confirmed to be real identifiers pulled from
    # PRAGMA table_info, so it's safe to interpolate them.
    selected = ", ".join(columns)

    sql = f"""
SELECT
    {selected}
FROM {table}
"""

    return sql.strip()


# ---------------------------------------------------------------------
# Load DataFrame
# ---------------------------------------------------------------------

def load_dataframe(sql: str) -> pd.DataFrame:

    connection = sqlite3.connect(
        settings.database_path
    )

    try:

        dataframe = pd.read_sql_query(
            sql,
            connection,
        )

    finally:

        connection.close()

    if dataframe.empty:

        raise ValueError("The query returned no rows.")

    return dataframe


# ---------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------

def execute_analysis(
    plan: dict,
    dataframe: pd.DataFrame,
):

    analysis = plan["analysis"]

    function = ANALYSIS_FUNCTIONS[analysis]

    return function(dataframe)


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def run_analysis_core(
    question: str,
    model_key: str | None = None,
    max_retries: int = 3,
):

    llm = build_llm(model_key)

    error_context = None

    last_error = ""

    for attempt in range(
        1,
        max_retries + 1,
    ):

        try:

            plan = plan_analysis(
                question,
                llm,
                error_context,
            )

            sql = build_sql(plan)

            dataframe = load_dataframe(sql)

            result = execute_analysis(
                plan,
                dataframe,
            )

            return {
                "ok": True,
                "question": question,
                "analysis": plan["analysis"],
                "columns": plan["columns"],
                "rows": len(dataframe),
                "sql": sql,
                "result": result,
                "attempts": attempt,
                "retried": attempt > 1,
                "error": None,
            }

        except Exception as e:

            last_error = str(e)

            error_context = last_error

    return {

        "ok": False,

        "question": question,

        "analysis": None,

        "columns": None,

        "sql": None,

        "result": None,

        "attempts": max_retries,

        "retried": True,

        "error": last_error,
    }