"""
src/eval/utils/evaluator.py

Generic benchmark runner. Category-specific behavior (which dataset,
which checker) is injected by the caller (see benchmarks/*.py) rather
than hardcoded here, so the same runner serves SQL, Analysis, and
Visualization benchmarks, and both the real agents and the baseline.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path
from typing import Callable


def run_benchmark(
    *,
    agent_name: str,
    dataset_file: Path,
    output_file: str,
    answer_function: Callable[[str], dict],
    checker_function: Callable[[dict, object], bool],
) -> list[dict]:
    with open(dataset_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)

    results = []
    correct = 0
    total_time = 0.0
    total_attempts = 0
    retry_count = 0
    difficulty_correct = defaultdict(int)
    difficulty_total = defaultdict(int)

    total_questions = len(questions)

    for i, q in enumerate(questions, start=1):
        print(f"[{agent_name}] Question {i}/{total_questions}: {q['question']}")

        start = time.perf_counter()
        try:
            answer = answer_function(q["question"])
        except Exception as e:
            answer = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        latency = time.perf_counter() - start
        total_time += latency

        gt = q.get("ground_truth")
        is_correct = gt is not None and checker_function(answer, gt)

        if is_correct:
            correct += 1

        difficulty = q.get("difficulty", "unknown")
        difficulty_total[difficulty] += 1
        if is_correct:
            difficulty_correct[difficulty] += 1

        attempts = answer.get("attempts", 1)
        retried = answer.get("retried", False)
        total_attempts += attempts
        if retried:
            retry_count += 1

        results.append({
            "id": q["id"],
            "category": q["category"],
            "task_type": q.get("task_type"),
            "difficulty": difficulty,
            "question": q["question"],
            "expected_agent": q.get("expected_agent"),
            "correct": is_correct,
            "ok": answer.get("ok", False),
            "latency_seconds": round(latency, 4),
            "attempts": attempts,
            "retried": retried,
            "answer": {k: v for k, v in answer.items() if k not in ("ok", "attempts", "retried")},
            "error": answer.get("error"),
        })

    output_path = Path(output_file)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)

    print()
    print("=" * 50)
    print(f"{agent_name.upper()} RESULTS")
    print("=" * 50)
    print(f"Questions:            {total_questions}")
    print(f"Correct answers:      {correct}")
    print(f"Accuracy:             {100 * correct / total_questions:.2f}%")
    print(f"Average latency:      {total_time / total_questions:.3f} s")
    print(f"Average attempts:     {total_attempts / total_questions:.2f}")
    print(f"Questions retried:    {retry_count}/{total_questions}")
    print()
    print("Accuracy by difficulty:")
    for difficulty in ("easy", "medium", "hard"):
        total = difficulty_total[difficulty]
        hits = difficulty_correct[difficulty]
        accuracy = 100 * hits / total if total else 0
        print(f"  {difficulty.capitalize():<7}{hits}/{total} ({accuracy:.2f}%)")
    print()
    print(f"Detailed results saved to: {output_path}")

    return results
