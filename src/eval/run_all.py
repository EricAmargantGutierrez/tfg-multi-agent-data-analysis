"""
src/eval/run_all.py

Runs the quantitative benchmarks in order: correctness (real agents +
baseline + monolithic, all 3 categories), then the pipeline benchmark
(latency + routing, one pass), then writes the summary.csv.

The Report Agent is not run here. It has no ground truth, so it is
checked by hand with a separate script:
    python -m src.eval.benchmarks.report_agent_benchmark [--language ...]

This makes real API calls. The results go under
results/eval/<TFG_MODEL>/<language>/.

Usage:
    python -m src.eval.run_all
    python -m src.eval.run_all --language es
    TFG_MODEL=ollama python -m src.eval.run_all --language ca
"""
import argparse

from src.eval.benchmarks.correctness_benchmark import run as run_correctness
from src.eval.benchmarks.pipeline_benchmark import run as run_pipeline
from src.eval.languages import DEFAULT_LANGUAGE, LANGUAGES
from src.eval.utils.metrics import build_summary, write_summary_csv

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", choices=LANGUAGES, default=DEFAULT_LANGUAGE,
                        help="Question language (default: en).")
    args = parser.parse_args()

    print(f"### 1/3: Correctness (agent + baseline + monolithic) [{args.language}] ###")
    run_correctness(language=args.language)

    print(f"\n### 2/3: Pipeline (latency + routing) [{args.language}] ###")
    run_pipeline(language=args.language)

    print(f"\n### 3/3: summary.csv [{args.language}] ###")
    rows = build_summary(args.language)
    write_summary_csv(rows, language=args.language)
