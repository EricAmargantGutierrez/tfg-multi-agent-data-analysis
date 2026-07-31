"""
src/eval/baselines/monolithic_agent.py

A second, stronger baseline than src.eval.baselines.single_agent: ONE
agent with access to all three real capabilities (SQL execution,
statistics, chart rendering) via a single combined system prompt. It
decides for itself, in one LLM call, which capability the question needs
and with what parameters -- then the REAL underlying code executes it
(src.core.db, src.agents.analysis.statistics, src.agents.viz.engine.render
-- the same code the specialized agents use, not a re-implementation).

Why this baseline exists, distinct from the minimal single_agent
baseline: the minimal baseline mostly measures "does having tools help
at all" (SQL-only vs. real Python statistics is a large, almost
guaranteed gap). This one holds capability constant -- it has the exact
same tools as the four specialized agents combined -- and only varies
the ARCHITECTURE: one agent deciding internally vs. a router + four
specialized agents. If the multi-agent system still wins against this,
that's a materially stronger claim about decomposition itself.

Self-correcting (like the real agents): a malformed action/spec is fed
back as an error and retried, using the same shared retry loop.
"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from src.agents.analysis.statistics import ANALYSIS_FUNCTIONS
from src.agents.viz.engine import render
from src.core.db import (
    build_select,
    get_schema,
    get_valid_columns,
    load_dataframe_readonly,
    run_readonly_query,
    run_readonly_query_dicts,
)
from src.core.llm_json import parse_llm_json
from src.core.retry import run_self_correcting
from src.llm import build_llm
from src.models.schemas import AnalysisPlan, ChartSpec

from src.agents.analysis.prompts import SYSTEM_PROMPT as _ANALYSIS_PROMPT
from src.agents.sql.prompts import SYSTEM_PROMPT as _SQL_PROMPT
from src.agents.viz.prompts import SYSTEM_PROMPT as _VIZ_PROMPT

# Built by embedding the three real specialized agents' prompts VERBATIM
# (imported, not retyped) rather than a hand-written summary. A summary
# was tried first and was a real methodological flaw: it was ~206 words
# vs. the real prompts' combined ~845 words, missing entire sections
# (SQL's worked ranking examples, Viz's warning against EXTRACT()/
# DATE_TRUNC()/MONTH()/YEAR(), Analysis's filter examples). If the
# monolithic agent had underperformed with that version, the result
# would have been uninterpretable -- unclear whether the gap was about
# architecture (one agent vs. four) or just less detailed prompting.
# Importing the real prompts also means this baseline can't silently
# drift out of sync if the specialized prompts are edited later.
SYSTEM_PROMPT = f"""
You are a data analysis assistant with THREE capabilities. For each
question, decide which ONE capability best answers it.

Below are the full instructions for each capability -- the SAME
instructions given to three separate specialized systems. You have all
three yourself and must choose which one to act as for this question.

=== CAPABILITY 1: SQL ===
{_SQL_PROMPT.strip()}

For this capability, return JSON as:
{{"action": "sql", "sql": "SELECT ..."}}

=== CAPABILITY 2: ANALYSIS ===
{_ANALYSIS_PROMPT.strip()}

For this capability, return the same JSON shape shown above, with an
added "action" field, e.g.:
{{"action": "analysis", "analysis": "mean", "columns": ["profit"], "filters": []}}

=== CAPABILITY 3: CHART ===
{_VIZ_PROMPT.strip()}

For this capability, return the same JSON shape shown above, with an
added "action" field, e.g.:
{{"action": "chart", "chart_type": "bar", "sql": "SELECT ...", "title": "...", "xlabel": "...", "ylabel": "..."}}

=== YOUR TASK ===
Choose exactly ONE capability for this question. Return ONLY the JSON
object for that capability, with the "action" field added as shown
above. Nothing else -- no explanation.
"""


def _execute_sql(spec: dict[str, Any]) -> dict[str, Any]:
    result = run_readonly_query(spec["sql"])
    return {"action": "sql", "columns": result["columns"], "rows": result["rows"], "sql": result["sql"]}


def _execute_analysis(spec: dict[str, Any], valid_columns: set[str]) -> dict[str, Any]:
    try:
        plan = AnalysisPlan(**{k: v for k, v in spec.items() if k != "action"})
    except ValidationError as e:
        raise ValueError(f"Invalid analysis spec: {e}") from e

    sql, params = build_select(
        columns=plan.columns,
        filters=[f.model_dump() for f in plan.filters],
        valid_columns=valid_columns,
    )
    dataframe = load_dataframe_readonly(sql, params)
    function = ANALYSIS_FUNCTIONS[plan.analysis]
    result = function(dataframe, target=plan.target) if plan.analysis == "regression" else function(dataframe)

    return {
        "action": "analysis", "analysis": plan.analysis, "columns": plan.columns,
        "target": plan.target, "filters": [f.model_dump() for f in plan.filters],
        "sql": sql, "result": result,
    }


def _execute_chart(spec: dict[str, Any]) -> dict[str, Any]:
    try:
        chart_spec = ChartSpec(**{k: v for k, v in spec.items() if k != "action"})
    except ValidationError as e:
        raise ValueError(f"Invalid chart spec: {e}") from e

    rows = run_readonly_query_dicts(chart_spec.sql)
    path = render(chart_spec, rows)
    return {"action": "chart", "path": path, "rows": rows, "spec": chart_spec.model_dump()}


def run_monolithic_agent(question: str, model_key: str | None = None, max_retries: int = 3) -> dict[str, Any]:
    llm = build_llm(model_key)
    schema = get_schema()
    valid_columns = get_valid_columns()

    def step(error_context: str | None) -> dict[str, Any]:
        prompt = f"Schema:\n\n{schema}\n\nQuestion:\n\n{question}"
        if error_context:
            prompt += f"\n\nPrevious attempt failed.\n\nError:\n\n{error_context}\n\nReturn corrected JSON only."

        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        spec = parse_llm_json(response.content)
        action = spec.get("action")

        if action == "sql":
            return _execute_sql(spec)
        if action == "analysis":
            return _execute_analysis(spec, valid_columns)
        if action == "chart":
            return _execute_chart(spec)
        raise ValueError(f"Unknown or missing action: {action!r} (must be sql, analysis, or chart)")

    return run_self_correcting(
        step,
        max_retries=max_retries,
        failure_defaults={"action": None, "columns": None, "rows": None, "result": None, "sql": None},
    )
