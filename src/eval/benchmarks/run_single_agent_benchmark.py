"""
src/eval/benchmarks/run_single_agent_benchmark.py

Runs the minimal baseline (src.eval.baselines.single_agent.run_single_agent)
against all three question sets. Same questions the real agents see, same
scoring principle (structured output, never prose) -- the only difference
is the baseline gets a generic prompt, no retry, and no specialized agent.

Usage:
    python -m src.eval.benchmarks.run_single_agent_benchmark
    python -m src.eval.benchmarks.run_single_agent_benchmark --only analysis visualization
"""
import argparse
from pathlib import Path

from src.eval.baselines.single_agent import run_single_agent
from src.eval.checks import check_baseline_analysis, check_baseline_sql_shaped
from src.eval.utils.evaluator import run_benchmark

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"

RUNS = [
    ("sql", "Baseline (SQL questions)", DATASETS_DIR / "sql_questions.json",
     "results/eval/baseline_sql_results.json", check_baseline_sql_shaped),
    ("analysis", "Baseline (Analysis questions)", DATASETS_DIR / "analysis_questions.json",
     "results/eval/baseline_analysis_results.json", check_baseline_analysis),
    ("visualization", "Baseline (Visualization questions)", DATASETS_DIR / "visualization_questions.json",
     "results/eval/baseline_visualization_results.json", check_baseline_sql_shaped),
]

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only", nargs="+", choices=["sql", "analysis", "visualization"],
        help="Only run these categories (e.g. to re-run after a rate limit "
             "cut off a partial run, without re-spending tokens on categories "
             "that already completed successfully).",
    )
    args = parser.parse_args()

    for key, agent_name, dataset_file, output_file, checker in RUNS:
        if args.only and key not in args.only:
            continue
        print(f"\n{'#' * 60}")
        print(f"# {agent_name}")
        print(f"{'#' * 60}\n")
        run_benchmark(
            agent_name=agent_name,
            dataset_file=dataset_file,
            output_file=output_file,
            answer_function=run_single_agent,
            checker_function=checker,
        )
