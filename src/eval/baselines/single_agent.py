"""
src/eval/baselines/single_agent.py

The baseline: same LLM, schema + question, ONE plain-language instruction
to write a single SQL query. No specialized system prompt, no retry, no
agent routing, no statistical/charting capability.

Deliberately does NOT reuse src/agents/sql/prompts.py's tuned prompt
(ranking-question rules, worked examples, aggregation conventions). If it
did, this would only measure "does the retry loop help" -- reusing the
tuned prompt would silently smuggle the real SQL Agent's prompt
engineering into the "baseline", understating the architecture's value.
The whole point of a baseline is a deliberately minimal comparison point.

Used across ALL question categories, not just SQL ones: for analysis and
visualization questions, this still only ever writes SQL. Whether it can
approximate the right answer this way (e.g. AVG for "mean") or simply
cannot express the question at all (correlation, PCA, KMeans have no
SQLite equivalent) is itself the finding the evaluation is measuring.
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
