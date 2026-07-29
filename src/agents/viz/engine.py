"""
src/agents/viz/engine.py

Visualization Agent core logic: a question that implies a chart -> a chart
spec (LLM decides WHAT to plot) -> deterministic Matplotlib rendering
(trusted code decides HOW). Correctness is checkable via the underlying
data, not by parsing the PNG.
"""
from __future__ import annotations

import uuid

import matplotlib
matplotlib.use("Agg")  # headless-safe; no effect on machines with a display
import matplotlib.pyplot as plt
from pydantic import ValidationError

from src.agents.viz.prompts import SYSTEM_PROMPT
from src.core.db import get_schema, run_readonly_query_dicts
from src.core.llm_json import parse_llm_json
from src.core.paths import RESULTS_DIR
from src.core.retry import run_self_correcting
from src.llm import build_llm
from src.models.schemas import ChartSpec


def render(spec: ChartSpec, rows: list[dict]) -> str:
    if not rows:
        raise ValueError("No rows returned.")

    chart = spec.chart_type
    keys = list(rows[0].keys())
    x = keys[0]
    y = keys[1] if len(keys) > 1 else None

    # Drop rows with a NULL in a plotted column -- matplotlib raises an
    # opaque TypeError on None labels/values rather than skipping them,
    # and a NULL category/value is a data-quality issue, not something
    # the chart itself should crash on.
    before = len(rows)
    rows = [r for r in rows if r[x] is not None and (y is None or r[y] is not None)]
    if not rows:
        raise ValueError("All rows had a NULL value in the plotted column(s).")
    dropped = before - len(rows)

    plt.figure(figsize=(8, 5))

    if chart == "bar":
        plt.bar([r[x] for r in rows], [r[y] for r in rows])
    elif chart == "line":
        plt.plot([r[x] for r in rows], [r[y] for r in rows], marker="o")
    elif chart == "scatter":
        plt.scatter([r[x] for r in rows], [r[y] for r in rows])
    elif chart == "pie":
        plt.pie([r[y] for r in rows], labels=[r[x] for r in rows], autopct="%1.1f%%")
    elif chart == "histogram":
        plt.hist([r[x] for r in rows], bins=20)
    elif chart == "boxplot":
        plt.boxplot([r[x] for r in rows], vert=True)

    plt.title(spec.title)
    if chart != "pie":
        plt.xlabel(spec.xlabel)
        plt.ylabel(spec.ylabel)
    plt.tight_layout()

    RESULTS_DIR.mkdir(exist_ok=True)
    output = RESULTS_DIR / f"{uuid.uuid4().hex}.png"
    plt.savefig(output)
    plt.close()
    return str(output)


def generate_chart_core(question: str, max_retries: int = 3) -> dict:
    llm = build_llm()
    schema = get_schema()

    def step(error_context: str | None) -> dict:
        prompt = f"Schema:\n\n{schema}\n\nQuestion:\n\n{question}"
        if error_context:
            prompt += f"\n\nPrevious attempt failed.\n\nError:\n\n{error_context}\n\nReturn corrected JSON only."

        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])
        raw = parse_llm_json(response.content)

        try:
            spec = ChartSpec(**raw)
        except ValidationError as e:
            raise ValueError(f"Invalid chart spec: {e}") from e

        rows = run_readonly_query_dicts(spec.sql)
        path = render(spec, rows)

        return {"path": path, "rows": rows, "spec": spec.model_dump()}

    return run_self_correcting(
        step,
        max_retries=max_retries,
        failure_defaults={"path": None, "rows": None, "spec": None},
    )
