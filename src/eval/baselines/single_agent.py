"""
src/eval/baselines/single_agent.py

The baseline: same LLM, same schema and question, but just ONE plain
instruction to write a single SQL query. No tuned system prompt, no
retry, no agent routing, no statistics or charting.

Deliberately does NOT reuse the Data Query Agent's tuned prompt - doing
so would sneak that prompt work into the "baseline" and understate the
architecture's value. A baseline only works if it stays minimal.

Used for ALL question categories, not just Data Query: for analysis and
visualization questions it still only writes SQL. Whether it can get
close (e.g. AVG for "mean") or can't express the question at all
(correlation, PCA, K-Means) is exactly what the evaluation measures.
"""
from __future__ import annotations

from typing import Any

from src.agents.safety import UnsafeSQLError
from src.core.db import get_schema, run_readonly_query
from src.llm import build_llm

MINIMAL_SYSTEM_PROMPT = """
You are a SQL assistant. Given a database schema and a question, write a
single SQL query that answers it as best you can.

Return ONLY the SQL query. No explanation, no markdown formatting.
"""


def run_single_agent(question: str, model_key: str | None = None) -> dict[str, Any]:
    llm = build_llm(model_key)
    schema = get_schema()

    response = llm.invoke([
        {"role": "system", "content": MINIMAL_SYSTEM_PROMPT},
        {"role": "user", "content": f"Schema:\n{schema}\n\nQuestion: {question}"},
    ])
    text = response.content if isinstance(response.content, str) else str(response.content)
    sql = text.replace("```sql", "").replace("```", "").strip()

    try:
        result = run_readonly_query(sql)
        result.update(ok=True, attempts=1, retried=False, error=None)
        return result
    except (UnsafeSQLError, Exception) as e:
        return {
            "ok": False, "columns": [], "rows": [], "sql": sql,
            "attempts": 1, "retried": False, "error": f"{type(e).__name__}: {e}",
        }
