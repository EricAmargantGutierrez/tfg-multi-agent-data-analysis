"""
src/eval/benchmarks/pipeline_benchmark.py

ONE pass through the real orchestrator (src.orchestrator.graph.answer())
for every question, capturing BOTH:
  - full end-to-end latency (router + agent + narrator), the number
    that's actually comparable to the baseline's single-call latency;
  - routing accuracy (did the router pick the expected agent?).

These used to be two separate scripts (pipeline_latency_benchmark.py and
the routing-check part of multiagent_benchmark.py) that each re-asked all
55 questions independently -- not useful, since both call graph.answer()
and the routing decision is already known the moment you time the call.

Does NOT re-score answer correctness -- that's correctness_benchmark.py,
which deliberately isolates each agent's own capability by calling it
directly, bypassing the router (so a misroute there wouldn't look like an
agent-capability failure). Here, correctness of the underlying answer is
irrelevant; only "did routing succeed" and "how long did it take" matter.

Usage:
    python -m src.eval.benchmarks.pipeline_benchmark
    python -m src.eval.benchmarks.pipeline_benchmark --categories analysis visualization
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from src.orchestrator.graph import answer

DATASETS_DIR = Path(__file__).resolve().parents[1] / "datasets"
OUTPUT_FILE = Path("results/eval/pipeline_results.json")

DATASET_FILES = {
    "sql": "sql_questions.json",
    "analysis": "analysis_questions.json",
    "visualization": "visualization_questions.json",
}


def _load_existing() -> list[dict]:
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def run(categories: list[str] | None = None) -> list[dict]:
    from src.eval.utils.warmup import warm_up

    categories = categories or list(DATASET_FILES.keys())

    existing = _load_existing()
    kept = [r for r in existing if r["category"] not in categories]
    if kept:
        print(f"Keeping {len(kept)} existing results from categories not being re-run: "
              f"{sorted({r['category'] for r in kept})}\n")

    new_results = []
    consecutive_failures = 0
    stopped_early = False

    for category in categories:
        if stopped_early:
            break

        with open(DATASETS_DIR / DATASET_FILES[category], encoding="utf-8") as f:
            questions = json.load(f)

        # graph.answer() routes internally to a different agent (each with
        # its own, differently-shaped system prompt) depending on the
        # question's category. A warm-up call using a SQL-style question
        # only exercises the SQL Agent's prompt -- the first
        # Analysis-routed and first Visualization-routed question in this
        # same run would each still pay their own unwarmed cost otherwise.
        # So: warm up per category, using a real question from THAT
        # category, right before its questions start.
        warm_up(lambda q: answer(q, []), question=questions[0]["question"])

        for q in questions:
            print(f"[Pipeline] {q['category']} #{q['id']}: {q['question']}")
            start = time.perf_counter()
            predicted_agent = None
            error_detail = None
            narrated_answer = None
            try:
                history: list = []
                out = answer(q["question"], history)
                ok = bool(out.get("ok", False))
                predicted_agent = history[-1]["agent"] if history else None
                narrated_answer = out.get("answer")
                if not ok:
                    error_detail = out.get("raw", {}).get("error")
            except Exception as e:
                ok = False
                error_detail = f"{type(e).__name__}: {e}"
                print(f"  (pipeline error, still timed: {error_detail})")
            latency = time.perf_counter() - start

            new_results.append({
                "id": q["id"],
                "category": q["category"],
                "question": q["question"],
                "expected_agent": q.get("expected_agent"),
                "predicted_agent": predicted_agent,
                "routing_correct": predicted_agent == q.get("expected_agent"),
                "latency_seconds": round(latency, 4),
                "error": error_detail,
                "narrated_answer": narrated_answer,
                "ok": ok,
            })

            consecutive_failures = 0 if ok else consecutive_failures + 1
            if consecutive_failures >= 3:
                print(f"\n{consecutive_failures} consecutive failures -- stopping early. "
                      "Check the 'error' field in the saved JSON for why (rate limit, "
                      "resource exhaustion, or a genuine model/routing failure all look "
                      "different there). Re-run the remaining categories with "
                      "--categories once resolved.")
                stopped_early = True
                break

    results = kept + new_results

    Path("results/eval").mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    _print_summary(results)
    return results


def _print_summary(results: list[dict]) -> None:
    print()
    print("=" * 50)
    print("PIPELINE BENCHMARK (latency + routing, one pass)")
    print("=" * 50)

    successful = [r for r in results if r["ok"]]
    failed_count = len(results) - len(successful)
    if failed_count:
        print(f"WARNING: {failed_count}/{len(results)} calls failed and are EXCLUDED "
              f"from latency averages below.")

    # Latency: successful calls only -- a fast failure is not a real measurement.
    if successful:
        avg_all = sum(r["latency_seconds"] for r in successful) / len(successful)
        print(f"\nLatency -- all categories: {avg_all:.3f}s avg (n={len(successful)} successful)")
        for category, filename in DATASET_FILES.items():
            subset = [r for r in successful if r["category"] == category]
            attempted = len([r for r in results if r["category"] == category])
            expected = len(json.load(open(DATASETS_DIR / filename, encoding="utf-8")))
            if subset:
                avg = sum(r["latency_seconds"] for r in subset) / len(subset)
                flag = "" if attempted == expected else f"  <-- INCOMPLETE, expected {expected}"
                print(f"  {category:<14}{avg:.3f}s avg (n={len(subset)}/{expected}){flag}")
            else:
                print(f"  {category:<14}NO SUCCESSFUL RUNS -- re-run with --categories {category}")
    else:
        print("\nNo successful calls at all -- nothing to average.")

    # Routing accuracy: computed regardless of whether the call itself
    # "ok"'d, since routing happens before agent execution.
    print(f"\nRouting accuracy -- all categories: "
          f"{sum(r['routing_correct'] for r in results)}/{len(results)} "
          f"({100*sum(r['routing_correct'] for r in results)/len(results):.1f}%)" if results else "n/a")
    for category in DATASET_FILES:
        subset = [r for r in results if r["category"] == category]
        if subset:
            correct = sum(r["routing_correct"] for r in subset)
            print(f"  {category:<14}{correct}/{len(subset)} ({100*correct/len(subset):.1f}%)")

    print()
    print("Detailed results saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--categories", nargs="+", choices=list(DATASET_FILES.keys()),
        help="Only re-run these categories; results for the others are "
             "kept from the existing results file untouched.",
    )
    args = parser.parse_args()
    run(categories=args.categories)
