"""
src/agents/sql/engine.py

SQL Agent core logic: natural language question -> read-only SQL ->
structured rows, self-correcting on error. The MCP wrapper (agent.py) is
a thin pass-through to run_sql_core().
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from src.agents.sql.prompts import SYSTEM_PROMPT
from src.core.db import DB_PATH, get_schema, run_readonly_query
from src.core.retry import run_self_correcting
from src.llm import build_llm


def generate_sql(question: str, schema: str, llm, error_context: str | None = None) -> str:
    user = f"Schema:\n{schema}\n\nQuestion: {question}"
    if error_context:
        user += (
            f"\n\nYour previous attempt failed with this error:\n{error_context}\n"
            "Return a corrected query. Output ONLY the SQL."
        )
    resp = llm.invoke(
        [{"role": "system", "content": SYSTEM_PROMPT},
         {"role": "user", "content": user}]
    )
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    return text.replace("```sql", "").replace("```", "").strip()


def run_sql_core(
    question: str,
    *,
    model_key: str | None = None,
    max_retries: int = 3,
    db_path: Path = DB_PATH,
) -> dict[str, Any]:
    llm = build_llm(model_key)
    schema = get_schema(db_path)

    def step(error_context: str | None) -> dict[str, Any]:
        sql = generate_sql(question, schema, llm, error_context)
        return run_readonly_query(sql, db_path)

    return run_self_correcting(
        step,
        max_retries=max_retries,
        failure_defaults={"columns": [], "rows": [], "sql": None},
    )
