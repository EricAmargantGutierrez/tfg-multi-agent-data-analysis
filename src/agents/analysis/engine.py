"""
src/agents/analysis/engine.py

Analysis Agent core logic. Pipeline:

Question -> LLM planner -> AnalysisPlan (analysis + columns + filters)
         -> src.core.db.build_select (validated, parameterized SQL)
         -> pandas DataFrame -> statistics.py -> structured result

The `filters` field is the fix for a real bug: previously the planner
could only select whole columns with no WHERE clause, so any question
with a condition in it ("average profit in the West region") silently
computed over the entire table. Filter values are bound as SQL
parameters (never string-interpolated), same defense-in-depth standard
as the rest of the codebase.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from pydantic import ValidationError

from src.agents.analysis.prompts import SYSTEM_PROMPT
from src.agents.analysis.statistics import ANALYSIS_FUNCTIONS
from src.core.db import build_select, get_schema, get_valid_columns, load_dataframe_readonly
from src.core.llm_json import parse_llm_json
from src.core.retry import run_self_correcting
from src.llm import build_llm
from src.models.schemas import AnalysisPlan


def plan_analysis(question: str, llm, error_context: str | None = None) -> AnalysisPlan:
    user_prompt = f"Database schema:\n\n{get_schema()}\n\nQuestion:\n\n{question}"
    if error_context:
        user_prompt += f"\n\nPrevious attempt failed.\n\nError:\n\n{error_context}\n\nReturn corrected JSON."

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ])
    raw = parse_llm_json(response.content)

    try:
        plan = AnalysisPlan(**raw)
    except ValidationError as e:
        raise ValueError(f"Invalid analysis plan: {e}") from e

    if plan.analysis not in ANALYSIS_FUNCTIONS:
        raise ValueError(f"Unknown analysis '{plan.analysis}'.")

    return plan


def execute_analysis(plan: AnalysisPlan, dataframe: pd.DataFrame) -> dict:
    function = ANALYSIS_FUNCTIONS[plan.analysis]
    return function(dataframe)


def run_analysis_core(question: str, model_key: str | None = None, max_retries: int = 3) -> dict[str, Any]:
    llm = build_llm(model_key)
    valid_columns = get_valid_columns()

    def step(error_context: str | None) -> dict[str, Any]:
        plan = plan_analysis(question, llm, error_context)

        sql, params = build_select(
            columns=plan.columns,
            filters=[f.model_dump() for f in plan.filters],
            valid_columns=valid_columns,
        )
        dataframe = load_dataframe_readonly(sql, params)
        result = execute_analysis(plan, dataframe)

        return {
            "question": question,
            "analysis": plan.analysis,
            "columns": plan.columns,
            "filters": [f.model_dump() for f in plan.filters],
            "rows": len(dataframe),
            "sql": sql,
            "result": result,
        }

    return run_self_correcting(
        step,
        max_retries=max_retries,
        failure_defaults={
            "question": question, "analysis": None, "columns": None,
            "filters": None, "sql": None, "result": None,
        },
    )
