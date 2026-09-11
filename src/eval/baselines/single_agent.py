"""
src/eval/baselines/single_agent.py

The baseline: same LLM, same schema and question, but just ONE plain
instruction to write a single SQL query. No tuned system prompt, no
retry, no agent routing, no statistics or charting.

On purpose, this does NOT reuse src/agents/data_query/prompts.py's tuned
prompt (its ranking-question rules, worked examples, aggregation
conventions). If it did, using the real prompt would sneak the real Data
Query Agent's prompt work into the "baseline" and make the architecture
look less useful than it is. A baseline is only useful if it stays a
deliberately minimal comparison point.

Used for ALL question categories, not just Data Query ones: for analysis
and visualization questions, it still only ever writes SQL. Whether it
can get close this way (e.g. `AVG` for "mean") or just can't express the
question at all (correlation, PCA, K-Means have no SQLite equivalent) is
exactly the thing the evaluation is trying to find out.
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
