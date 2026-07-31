"""
src/eval/benchmarks/correctness_benchmark.py

Correctness comparison across THREE points, all three categories, in one
file:
  - "agent": the real specialized agents (forced routing, isolates each
    agent's own capability -- routing accuracy is measured separately,
    in pipeline_benchmark.py).
  - "baseline": a minimal single LLM, one plain SQL query, no tools.
    Isolates "does having any specialized tooling help at all."
  - "monolithic": a single LLM with the SAME tools as the four
    specialized agents combined (SQL, statistics, charting), deciding
    for itself which to use. Isolates "does SPLITTING those tools across
    separate agents + routing add value, beyond just having them
    available to one agent."

Usage:
    python -m src.eval.benchmarks.correctness_benchmark
    python -m src.eval.benchmarks.correctness_benchmark --side agent
    python -m src.eval.benchmarks.correctness_benchmark --side baseline
    python -m src.eval.benchmarks.correctness_benchmark --side monolithic
    python -m src.eval.benchmarks.correctness_benchmark --categories analysis
"""
from __future__ import annotations

import argparse
from pathlib import Path

from src.agents.analysis.engine import run_analysis_core
from src.agents.sql.engine import run_sql_core
from src.agents.viz.engine import generate_chart_core
from src.eval.baselines.monolithic_agent import run_monolithic_agent
from src.eval.baselines.single_agent import run_single_agent
from src.eval.checks import (
    check_analysis,
    check_baseline_analysis,
    check_baseline_sql_shaped,
    check_chart_data,
    check_monolithic_analysis,
    check_monolithic_rows,
    check_sql,
)
from src.eval.utils.evaluator import run_benchmark

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"


def _analysis_answer_fn(question: str) -> dict:
    result = run_analysis_core(question)
    return {
        "ok": result["ok"], "result": result.get("result"),
        "analysis": result.get("analysis"), "columns": result.get("columns"),
        "target": result.get("target"), "filters": result.get("filters"),
        "sql": result.get("sql"), "attempts": result["attempts"],
        "retried": result["retried"], "error": result.get("error"),
    }


# category -> (dataset file, real-agent fn, real-agent checker,
#              baseline checker, monolithic checker)
CATEGORIES = {
    "sql": (
        "sql_questions.json", run_sql_core, check_sql,
        check_baseline_sql_shaped, check_monolithic_rows,
    ),
    "analysis": (
        "analysis_questions.json", _analysis_answer_fn, check_analysis,
        check_baseline_analysis, check_monolithic_analysis,
    ),
    "visualization": (
        "visualization_questions.json", generate_chart_core, check_chart_data,
        check_baseline_sql_shaped, check_monolithic_rows,
    ),
}

ALL_SIDES = ["agent", "baseline", "monolithic"]


def run(side: str | None = None, categories: list[str] | None = None) -> None:
    from src.eval.utils.warmup import warm_up

    categories = categories or list(CATEGORIES.keys())
    sides = [side] if side else ALL_SIDES

    for category in categories:
        dataset_file, agent_fn, agent_checker, baseline_checker, monolithic_checker = CATEGORIES[category]
        dataset_path = DATASETS_DIR / dataset_file

        if "agent" in sides:
            warm_up(agent_fn)
            run_benchmark(
                agent_name=f"{category.capitalize()} Agent",
                dataset_file=dataset_path,
                output_file=f"results/eval/{category}_agent_results.json",
                answer_function=agent_fn,
                checker_function=agent_checker,
            )

        if "baseline" in sides:
            warm_up(run_single_agent)
            run_benchmark(
                agent_name=f"Baseline ({category})",
                dataset_file=dataset_path,
                output_file=f"results/eval/baseline_{category}_results.json",
                answer_function=run_single_agent,
                checker_function=baseline_checker,
            )

        if "monolithic" in sides:
            warm_up(run_monolithic_agent)
            run_benchmark(
                agent_name=f"Monolithic ({category})",
                dataset_file=dataset_path,
                output_file=f"results/eval/monolithic_{category}_results.json",
                answer_function=run_monolithic_agent,
                checker_function=monolithic_checker,
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--side", choices=ALL_SIDES,
                         help="Only run this side (default: all three).")
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES.keys()),
                         help="Only run these categories (default: all three).")
    args = parser.parse_args()
    run(side=args.side, categories=args.categories)
