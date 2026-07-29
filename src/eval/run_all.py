"""
src/eval/run_all.py

Runs the complete evaluation: routing accuracy, all three real-agent
benchmarks, all three baseline benchmarks, then aggregates everything
into results/eval/summary.csv.

This makes real LLM API calls (one per question per benchmark). Costs
scale with your model choice -- see docs/architecture.md / MIGRATION.md
for the cost discussion. Recommended: run once on Groq (free) to sanity
check everything works end-to-end before running paid models.

Usage:
    python -m src.eval.run_all
    TFG_MODEL=anthropic python -m src.eval.run_all
"""
from src.eval.benchmarks.multiagent_benchmark import run_all_agent_benchmarks, run_routing_benchmark
from src.eval.benchmarks.run_single_agent_benchmark import RUNS as BASELINE_RUNS
from src.eval.utils.evaluator import run_benchmark
from src.eval.utils.metrics import build_summary, write_summary_csv

if __name__ == "__main__":
    print("### 1/4: Routing accuracy ###")
    run_routing_benchmark()

    print("\n### 2/4: Real agent benchmarks (correct agent forced) ###")
    run_all_agent_benchmarks()

    print("\n### 3/4: Baseline benchmarks ###")
    for key, agent_name, dataset_file, output_file, checker in BASELINE_RUNS:
        from src.eval.baselines.single_agent import run_single_agent
        run_benchmark(
            agent_name=agent_name, dataset_file=dataset_file,
            output_file=output_file, answer_function=run_single_agent,
            checker_function=checker,
        )

    print("\n### 4/4: Aggregating summary.csv ###")
    rows = build_summary()
    write_summary_csv(rows)
