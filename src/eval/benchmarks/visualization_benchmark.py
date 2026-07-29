"""Runs the real Visualization Agent (src.agents.viz.engine.generate_chart_core)
against src/eval/datasets/visualization_questions.json.

Scores the DATA the chart was built from, never the rendered PNG.

Usage: python -m src.eval.benchmarks.visualization_benchmark
"""
from pathlib import Path

from src.agents.viz.engine import generate_chart_core
from src.eval.checks import check_chart_data
from src.eval.utils.evaluator import run_benchmark

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "visualization_questions.json"

if __name__ == "__main__":
    run_benchmark(
        agent_name="Visualization Agent",
        dataset_file=DATASET,
        output_file="results/eval/visualization_agent_results.json",
        answer_function=generate_chart_core,
        checker_function=check_chart_data,
    )
