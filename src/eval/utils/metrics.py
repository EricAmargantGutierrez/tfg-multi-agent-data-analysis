"""
src/eval/utils/metrics.py

Aggregates every results/eval/*.json file produced by the benchmarks into
one summary.csv: the table your Results chapter draws from. Computes,
per category, the headline comparison the whole evaluation exists to
answer:

    full_system_correctness - baseline_correctness = value of the architecture

Usage: python -m src.eval.utils.metrics
(run after correctness_benchmark.py and pipeline_benchmark.py)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

RESULTS_DIR = Path("results/eval")

FILES = {
    "sql": ("sql_agent_results.json", "baseline_sql_results.json", "monolithic_sql_results.json"),
    "analysis": ("analysis_agent_results.json", "baseline_analysis_results.json", "monolithic_analysis_results.json"),
    "visualization": ("visualization_agent_results.json", "baseline_visualization_results.json", "monolithic_visualization_results.json"),
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


def _pipeline_results() -> list[dict] | None:
    return _load(RESULTS_DIR / "pipeline_results.json")


def _pipeline_latency_by_category(category: str) -> float | None:
    """Full router+agent+narrator latency. Distinct from avg_latency_s,
    which only measures the agent's own *_core() execution time
    (bypassing router/narrator to isolate the agent's capability for
    scoring). This is the number that's actually comparable to the
    baseline's single-call latency. Only successful calls are averaged --
    a fast failure (e.g. a rate limit) is not a real latency measurement."""
    results = _pipeline_results()
    if not results:
        return None
    subset = [r for r in results if r.get("category") == category and r.get("ok")]
    if not subset:
        return None
    return sum(r["latency_seconds"] for r in subset) / len(subset)


def _routing_accuracy_by_category(category: str | None = None) -> float | None:
    results = _pipeline_results()
    if not results:
        return None
    subset = [r for r in results if category is None or r.get("category") == category]
    if not subset:
        return None
    return 100 * sum(r["routing_correct"] for r in subset) / len(subset)


def build_summary() -> list[dict]:
    rows = []

    for category, (agent_file, baseline_file, monolithic_file) in FILES.items():
        agent_results = _load(RESULTS_DIR / agent_file)
        baseline_results = _load(RESULTS_DIR / baseline_file)
        monolithic_results = _load(RESULTS_DIR / monolithic_file)

        agent_acc = _accuracy(agent_results) if agent_results else None
        baseline_acc = _accuracy(baseline_results) if baseline_results else None
        monolithic_acc = _accuracy(monolithic_results) if monolithic_results else None
        pipeline_latency = _pipeline_latency_by_category(category)
        routing_acc = _routing_accuracy_by_category(category)

        row = {
            "category": category,
            "n_questions": len(agent_results) if agent_results else 0,
            "system_correctness_pct": round(agent_acc, 2) if agent_acc is not None else None,
            "baseline_correctness_pct": round(baseline_acc, 2) if baseline_acc is not None else None,
            "monolithic_correctness_pct": round(monolithic_acc, 2) if monolithic_acc is not None else None,
            "architecture_value_pct": (
                round(agent_acc - baseline_acc, 2)
                if agent_acc is not None and baseline_acc is not None else None
            ),
            "decomposition_value_pct": (
                round(agent_acc - monolithic_acc, 2)
                if agent_acc is not None and monolithic_acc is not None else None
            ),
            "routing_accuracy_pct": round(routing_acc, 2) if routing_acc is not None else None,
            "avg_latency_s": round(_avg_latency(agent_results), 3) if agent_results else None,
            "full_pipeline_avg_latency_s": round(pipeline_latency, 3) if pipeline_latency is not None else None,
            "baseline_avg_latency_s": round(_avg_latency(baseline_results), 3) if baseline_results else None,
            "monolithic_avg_latency_s": round(_avg_latency(monolithic_results), 3) if monolithic_results else None,
            "retry_rate_pct": round(_retry_rate(agent_results), 2) if agent_results else None,
            "retry_success_rate_pct": (
                round(_retry_success_rate(agent_results), 2)
                if agent_results and _retry_success_rate(agent_results) is not None else None
            ),
        }
        for difficulty in ("easy", "medium", "hard"):
            val = _accuracy_by_difficulty(agent_results, difficulty) if agent_results else None
            row[f"correctness_{difficulty}_pct"] = round(val, 2) if val is not None else None
            baseline_val = _accuracy_by_difficulty(baseline_results, difficulty) if baseline_results else None
            row[f"baseline_correctness_{difficulty}_pct"] = round(baseline_val, 2) if baseline_val is not None else None

        rows.append(row)

    overall_routing = _routing_accuracy_by_category(None)
    if overall_routing is not None:
        pipeline_results = _pipeline_results()
        routing_row = {
            "category": "routing (all categories)",
            "n_questions": len(pipeline_results),
            "system_correctness_pct": round(overall_routing, 2),
            "baseline_correctness_pct": None,
            "monolithic_correctness_pct": None,
            "architecture_value_pct": None,
            "decomposition_value_pct": None,
            "routing_accuracy_pct": round(overall_routing, 2),
            "avg_latency_s": None,
            "full_pipeline_avg_latency_s": round(_avg_latency([r for r in pipeline_results if r["ok"]]), 3),
            "baseline_avg_latency_s": None,
            "monolithic_avg_latency_s": None,
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
        print(f"  {row['category']}: agent={row['system_correctness_pct']}% "
              f"baseline={row['baseline_correctness_pct']}% "
              f"monolithic={row['monolithic_correctness_pct']}%  "
              f"value_vs_baseline={row['architecture_value_pct']}%  "
              f"value_vs_monolithic={row['decomposition_value_pct']}%  "
              f"routing={row['routing_accuracy_pct']}%")


if __name__ == "__main__":
    rows = build_summary()
    write_summary_csv(rows)
