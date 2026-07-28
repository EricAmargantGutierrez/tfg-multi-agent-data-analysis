"""
src/models/schemas.py

Pydantic models for the structured objects LLMs are asked to produce.
Replaces the previous hand-rolled `if "x" not in plan: raise ValueError(...)`
checks scattered across the engines.

AnalysisPlan.filters is the fix for a real correctness bug: the previous
planner could only ever SELECT whole columns with no WHERE clause, so any
analysis question with a condition in it ("average profit in the West
region") silently computed over the entire table and returned ok=True.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

FilterOp = Literal["=", "!=", ">", ">=", "<", "<=", "LIKE", "IN", "BETWEEN"]


class Filter(BaseModel):
    column: str
    op: FilterOp
    value: Any

    @field_validator("value")
    @classmethod
    def _check_value_shape(cls, value, info):
        op = info.data.get("op")
        if op == "IN" and not (isinstance(value, list) and len(value) > 0):
            raise ValueError("op='IN' requires a non-empty list value.")
        if op == "BETWEEN" and not (isinstance(value, list) and len(value) == 2):
            raise ValueError("op='BETWEEN' requires a 2-element list value.")
        return value


class AnalysisPlan(BaseModel):
    analysis: str
    columns: list[str] = Field(min_length=1)
    filters: list[Filter] = Field(default_factory=list)

    @field_validator("columns")
    @classmethod
    def _normalize_columns(cls, columns: list[str]) -> list[str]:
        return [c.lower().replace(" ", "_") for c in columns]


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "pie", "histogram", "boxplot"]
    sql: str
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""


class RoutingDecision(BaseModel):
    agent: Literal["sql", "analysis", "viz", "report"]
