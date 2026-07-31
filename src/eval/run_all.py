"""
src/eval/run_all.py

Runs the complete quantitative evaluation: correctness (real agents +
baseline, all 3 categories), the full pipeline (latency + routing
accuracy, one pass), then aggregates everything into
results/eval/summary.csv.

The Report Agent is NOT included here -- it's evaluated qualitatively,
not against ground truth, via a separate script:
    python -m src.eval.benchmarks.report_agent_benchmark

This makes real LLM API calls. Recommended: run once on a fast/free
model to sanity check everything works end-to-end before running slower
or paid models.

Usage:
    python -m src.eval.run_all
    TFG_MODEL=ollama python -m src.eval.run_all
"""
from src.eval.benchmarks.correctness_benchmark import run as run_correctness
from src.eval.benchmarks.pipeline_benchmark import run as run_pipeline
from src.eval.utils.metrics import build_summary, write_summary_csv

if __name__ == "__main__":
    print("### 1/3: Correctness (real agents + baseline) ###")
    run_correctness()

    print("\n### 2/3: Pipeline (latency + routing accuracy, one pass) ###")
    run_pipeline()

    print("\n### 3/3: Aggregating summary.csv ###")
    rows = build_summary()
    write_summary_csv(rows)
