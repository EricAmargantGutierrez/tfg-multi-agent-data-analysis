"""
src/models/schemas.py

Pydantic models for the structured objects LLMs are asked to produce.
Replaces the previous hand-rolled `if "x" not in plan: raise ValueError(...)`
checks scattered across the engines.

AnalysisPlan.filters is the fix for a real correctness bug: the previous
planner could only ever SELECT whole columns with no WHERE clause, so any
analysis question with a condition in it ("average profit in the West
region") silently computed over the entire table and returned ok=True.

AnalysisPlan.target is the fix for a second real correctness bug: the
regression function used to treat "the last column in the list" as the
prediction target. That's an implicit convention the LLM has no reason to
know about -- it naturally lists columns in question order ("predict
profit from sales, discount, quantity" -> profit first), which silently
swapped the regression target and produced a low-r2 result with no error.
`target` makes this an explicit, named field instead of a positional
convention, so it can't be silently wrong.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
    target: str | None = None
    filters: list[Filter] = Field(default_factory=list)

    @field_validator("columns")
    @classmethod
    def _normalize_columns(cls, columns: list[str]) -> list[str]:
        return [c.lower().replace(" ", "_") for c in columns]

    @field_validator("target")
    @classmethod
    def _normalize_target(cls, target: str | None) -> str | None:
        return target.lower().replace(" ", "_") if target else target

    @model_validator(mode="after")
    def _require_target_for_regression(self) -> "AnalysisPlan":
        if self.analysis == "regression":
            if not self.target:
                raise ValueError(
                    "analysis='regression' requires a 'target' field naming "
                    "the column to predict (the other columns are predictors)."
                )
            if self.target not in self.columns:
                self.columns = [*self.columns, self.target]
        return self


class ChartSpec(BaseModel):
    chart_type: Literal["bar", "line", "scatter", "pie", "histogram", "boxplot"]
    sql: str
    title: str = ""
    xlabel: str = ""
    ylabel: str = ""


class RoutingDecision(BaseModel):
    agent: Literal["sql", "analysis", "viz", "report"]
