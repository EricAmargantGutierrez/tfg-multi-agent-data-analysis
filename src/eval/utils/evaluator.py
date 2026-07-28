from __future__ import annotations

import json
import time
from collections import defaultdict
from pathlib import Path


QUESTIONS_FILE = Path(__file__).parent / "evaluation_questions.json"


def run_benchmark(
    *,
    agent_name: str,
    output_file: str,
    answer_function,
):

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    Path("results").mkdir(exist_ok=True)

    results = []

    correct = 0
    total_time = 0.0

    total_attempts = 0
    retry_count = 0

    difficulty_correct = defaultdict(int)
    difficulty_total = defaultdict(int)

    total_questions = len(questions)

    for i, q in enumerate(questions, start=1):

        print(f"Question {i}/{total_questions}...")

        start = time.perf_counter()

        answer = answer_function(q["question"])

        latency = time.perf_counter() - start

        total_time += latency

        ok = (
            answer["ok"]
            and answer["rows"] == q["ground_truth"]
        )

        if ok:
            correct += 1

        difficulty_total[q["difficulty"]] += 1

        if ok:
            difficulty_correct[q["difficulty"]] += 1

        attempts = answer.get("attempts", 1)
        retried = answer.get("retried", False)

        total_attempts += attempts

        if retried:
            retry_count += 1

        results.append(
            {
                "id": q["id"],
                "category": q["category"],
                "difficulty": q["difficulty"],
                "question": q["question"],

                "correct": ok,

                "latency_seconds": round(latency, 4),

                "attempts": attempts,
                "retried": retried,

                "generated_sql": answer.get("sql"),

                "expected_rows": q["ground_truth"],
                "generated_rows": answer["rows"],

                "error": answer.get("error"),
            }
        )

    output_path = Path(output_file)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print()
    print("=" * 45)
    print(f"{agent_name.upper()} RESULTS")
    print("=" * 45)

    print(f"Questions:            {total_questions}")
    print(f"Correct answers:      {correct}")
    print(f"Accuracy:             {100 * correct / total_questions:.2f}%")
    print(f"Average latency:      {total_time / total_questions:.3f} s")
    print(f"Average attempts:     {total_attempts / total_questions:.2f}")
    print(f"Questions retried:    {retry_count}/{total_questions}")

    print()
    print("Accuracy by difficulty:")

    for difficulty in ["easy", "medium", "hard"]:

        total = difficulty_total[difficulty]
        hits = difficulty_correct[difficulty]

        accuracy = 100 * hits / total if total else 0

        print(
            f"  {difficulty.capitalize():<7}"
            f"{hits}/{total} ({accuracy:.2f}%)"
        )

    print()
    print(f"Detailed results saved to:")
    print(f"  {output_path}")