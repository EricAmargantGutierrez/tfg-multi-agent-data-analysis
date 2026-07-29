"""
src/eval/benchmarks/multiagent_benchmark.py

Two things this measures that the per-agent benchmarks don't:
  1. Routing accuracy: for every question across all three categories,
     does src.orchestrator.router.route() pick the expected_agent? This
     is checked independently of whether the chosen agent then answered
     correctly -- routing and answering are different failure modes and
     should be scored separately.
  2. Runs the three per-category agent benchmarks (which call each
     engine's *_core() function directly, forcing the correct agent --
     i.e. testing each agent's own capability in isolation) so a single
     command produces the full multi-agent-side picture.

Usage: python -m src.eval.benchmarks.multiagent_benchmark
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from src.orchestrator.router import route

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
DATASET_FILES = ["sql_questions.json", "analysis_questions.json", "visualization_questions.json"]


def run_routing_benchmark() -> list[dict]:
    results = []
    for filename in DATASET_FILES:
        with open(DATASETS_DIR / filename, encoding="utf-8") as f:
            questions = json.load(f)

        for q in questions:
            start = time.perf_counter()
            try:
                predicted = route(q["question"])
            except Exception as e:
                predicted = f"ERROR: {e}"
            latency = time.perf_counter() - start

            results.append({
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "expected_agent": q["expected_agent"],
                "predicted_agent": predicted,
                "correct": predicted == q["expected_agent"],
                "latency_seconds": round(latency, 4),
            })

    Path("results/eval").mkdir(parents=True, exist_ok=True)
    with open("results/eval/routing_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    total = len(results)
    correct = sum(r["correct"] for r in results)
    print(f"\nRouting accuracy: {correct}/{total} ({100 * correct / total:.2f}%)")
    for category in ("sql", "analysis", "visualization"):
        cat_results = [r for r in results if r["category"] == category]
        cat_correct = sum(r["correct"] for r in cat_results)
        print(f"  {category:<14}{cat_correct}/{len(cat_results)}")

    return results


def run_all_agent_benchmarks() -> None:
    # Imported lazily: importing these at module load time would pull in
    # fastmcp/agent wiring even when someone just wants routing numbers.
    from src.eval.benchmarks.sql_benchmark import DATASET as SQL_DATASET
    from src.eval.benchmarks.analysis_benchmark import DATASET as ANALYSIS_DATASET
    from src.eval.benchmarks.analysis_benchmark import answer_function as analysis_answer_fn
    from src.eval.benchmarks.visualization_benchmark import DATASET as VIZ_DATASET
    from src.agents.sql.engine import run_sql_core
    from src.agents.viz.engine import generate_chart_core
    from src.eval.checks import check_analysis, check_chart_data, check_sql
    from src.eval.utils.evaluator import run_benchmark

    run_benchmark(agent_name="SQL Agent", dataset_file=SQL_DATASET,
                  output_file="results/eval/sql_agent_results.json",
                  answer_function=run_sql_core, checker_function=check_sql)

    run_benchmark(agent_name="Analysis Agent", dataset_file=ANALYSIS_DATASET,
                  output_file="results/eval/analysis_agent_results.json",
                  answer_function=analysis_answer_fn, checker_function=check_analysis)

    run_benchmark(agent_name="Visualization Agent", dataset_file=VIZ_DATASET,
                  output_file="results/eval/visualization_agent_results.json",
                  answer_function=generate_chart_core, checker_function=check_chart_data)


if __name__ == "__main__":
    print("### Routing accuracy ###")
    run_routing_benchmark()
    print("\n### Per-agent capability (correct agent forced, not routed) ###")
    run_all_agent_benchmarks()
