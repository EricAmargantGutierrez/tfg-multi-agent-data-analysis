"""Runs the real SQL Agent (src.agents.sql.engine.run_sql_core) against
src/eval/datasets/sql_questions.json.

Usage: python -m src.eval.benchmarks.sql_benchmark
"""
from pathlib import Path

from src.agents.sql.engine import run_sql_core
from src.eval.checks import check_sql
from src.eval.utils.evaluator import run_benchmark

DATASET = Path(__file__).resolve().parents[1] / "datasets" / "sql_questions.json"

if __name__ == "__main__":
    run_benchmark(
        agent_name="SQL Agent",
        dataset_file=DATASET,
        output_file="results/eval/sql_agent_results.json",
        answer_function=run_sql_core,
        checker_function=check_sql,
    )
