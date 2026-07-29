"""
src/eval/utils/metrics.py

Aggregates every results/eval/*.json file produced by the benchmarks into
one summary.csv: the table your Results chapter draws from. Computes,
per category, the headline comparison the whole evaluation exists to
answer:

    full_system_correctness - baseline_correctness = value of the architecture

Usage: python -m src.eval.utils.metrics
(run after multiagent_benchmark.py and run_single_agent_benchmark.py)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RESULTS_DIR = Path("results/eval")

FILES = {
    "sql": ("sql_agent_results.json", "baseline_sql_results.json"),
    "analysis": ("analysis_agent_results.json", "baseline_analysis_results.json"),
    "visualization": ("visualization_agent_results.json", "baseline_visualization_results.json"),
}


def _load(path: Path) -> list[dict] | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _accuracy(results: list[dict]) -> float:
    if not results:
        return 0.0
    return 100 * sum(r["correct"] for r in results) / len(results)


def _accuracy_by_difficulty(results: list[dict], difficulty: str) -> float | None:
    subset = [r for r in results if r.get("difficulty") == difficulty]
    if not subset:
        return None
    return 100 * sum(r["correct"] for r in subset) / len(subset)


def _avg_latency(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(r["latency_seconds"] for r in results) / len(results)


def _retry_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    return 100 * sum(r.get("retried", False) for r in results) / len(results)


def _retry_success_rate(results: list[dict]) -> float | None:
    retried = [r for r in results if r.get("retried")]
    if not retried:
        return None
    return 100 * sum(r["correct"] for r in retried) / len(retried)


def build_summary() -> list[dict]:
    rows = []

    for category, (agent_file, baseline_file) in FILES.items():
        agent_results = _load(RESULTS_DIR / agent_file)
        baseline_results = _load(RESULTS_DIR / baseline_file)

        agent_acc = _accuracy(agent_results) if agent_results else None
        baseline_acc = _accuracy(baseline_results) if baseline_results else None

        row = {
            "category": category,
            "n_questions": len(agent_results) if agent_results else 0,
            "system_correctness_pct": round(agent_acc, 2) if agent_acc is not None else None,
            "baseline_correctness_pct": round(baseline_acc, 2) if baseline_acc is not None else None,
            "architecture_value_pct": (
                round(agent_acc - baseline_acc, 2)
                if agent_acc is not None and baseline_acc is not None else None
            ),
            "avg_latency_s": round(_avg_latency(agent_results), 3) if agent_results else None,
            "baseline_avg_latency_s": round(_avg_latency(baseline_results), 3) if baseline_results else None,
            "retry_rate_pct": round(_retry_rate(agent_results), 2) if agent_results else None,
            "retry_success_rate_pct": (
                round(_retry_success_rate(agent_results), 2)
                if agent_results and _retry_success_rate(agent_results) is not None else None
            ),
        }
        for difficulty in ("easy", "medium", "hard"):
            val = _accuracy_by_difficulty(agent_results, difficulty) if agent_results else None
            row[f"correctness_{difficulty}_pct"] = round(val, 2) if val is not None else None
            # Baseline never retries by design (see baselines/single_agent.py) --
            # included explicitly so the per-difficulty degradation pattern can
            # be compared side-by-side with the real agent's, not just guessed
            # at from the console printout.
            baseline_val = _accuracy_by_difficulty(baseline_results, difficulty) if baseline_results else None
            row[f"baseline_correctness_{difficulty}_pct"] = round(baseline_val, 2) if baseline_val is not None else None

        rows.append(row)

    routing_results = _load(RESULTS_DIR / "routing_results.json")
    if routing_results:
        routing_row = {
            "category": "routing (all categories)",
            "n_questions": len(routing_results),
            "system_correctness_pct": round(_accuracy(routing_results), 2),
            "baseline_correctness_pct": None,
            "architecture_value_pct": None,
            "avg_latency_s": round(_avg_latency(routing_results), 3),
            "baseline_avg_latency_s": None,
            "retry_rate_pct": None,
            "retry_success_rate_pct": None,
            "correctness_easy_pct": None,
            "correctness_medium_pct": None,
            "correctness_hard_pct": None,
            "baseline_correctness_easy_pct": None,
            "baseline_correctness_medium_pct": None,
            "baseline_correctness_hard_pct": None,
        }
        rows.append(routing_row)

    return rows


def write_summary_csv(rows: list[dict], output_file: str = "results/eval/summary.csv") -> None:
    if not rows:
        print("No result files found -- run the benchmarks first.")
        return

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Summary written to {output_path}\n")
    for row in rows:
        print(f"  {row['category']}: system={row['system_correctness_pct']}% "
              f"baseline={row['baseline_correctness_pct']}% "
              f"value={row['architecture_value_pct']}%  "
              f"| latency system={row['avg_latency_s']}s baseline={row['baseline_avg_latency_s']}s")


if __name__ == "__main__":
    rows = build_summary()
    write_summary_csv(rows)
