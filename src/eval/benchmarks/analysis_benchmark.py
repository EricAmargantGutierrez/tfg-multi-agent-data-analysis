"""Runs the real Analysis Agent (src.agents.analysis.engine.run_analysis_core)
against src/eval/datasets/analysis_questions.json.

Usage: python -m src.eval.benchmarks.analysis_benchmark
"""
from pathlib import Path

from src.agents.analysis.engine import run_analysis_core
from src.eval.checks import check_analysis
from src.eval.utils.evaluator import run_benchmark

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "analysis_questions.json"


def answer_function(question: str) -> dict:
    result = run_analysis_core(question)
    # check_analysis only needs "result", but the rest (columns, filters,
    # sql) is what you need on hand to diagnose *why* a wrong answer went
    # wrong -- e.g. did the planner pick different/reordered columns than
    # the reference? Without these, a failed regression/PCA/KMeans is a
    # dead end for failure analysis.
    return {"ok": result["ok"], "result": result.get("result"),
            "analysis": result.get("analysis"), "columns": result.get("columns"),
            "filters": result.get("filters"), "sql": result.get("sql"),
            "attempts": result["attempts"], "retried": result["retried"],
            "error": result.get("error")}


if __name__ == "__main__":
    run_benchmark(
        agent_name="Analysis Agent",
        dataset_file=DATASET,
        output_file="results/eval/analysis_agent_results.json",
        answer_function=answer_function,
        checker_function=check_analysis,
    )
