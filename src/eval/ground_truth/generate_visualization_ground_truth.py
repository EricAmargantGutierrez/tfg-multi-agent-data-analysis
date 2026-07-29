"""
src/eval/ground_truth/generate_visualization_ground_truth.py

Executes each question's hand-written reference SQL and stores the
resulting data as ground_truth. Correctness for a chart is checked
against the DATA it was built from, never the rendered PNG -- same
principle the guide established for the Viz Agent itself.

Run once, after `python -m src.ingest`, and whenever the dataset changes:
    python -m src.eval.ground_truth.generate_visualization_ground_truth
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.config.settings import settings
from src.core.db import MAX_ROWS

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "datasets" / "visualization_questions.json"


def execute_query(sql: str) -> list[list]:
    connection = sqlite3.connect(settings.database_path)
    try:
        cursor = connection.execute(sql)
        # Capped identically to src.core.db.run_readonly_query_dicts, which
        # is what the real Viz Agent actually uses. Ground truth must
        # reflect what the system can structurally return -- for a chart
        # over more than MAX_ROWS points, the agent silently truncates,
        # and comparing it against an uncapped "true" answer would be
        # comparing it against a target it was never going to hit.
        rows = cursor.fetchmany(MAX_ROWS)
        return [list(row) for row in rows]
    finally:
        connection.close()


def main() -> None:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Generating ground truth for {len(questions)} visualization questions...\n")

    for i, question in enumerate(questions, start=1):
        print(f"Question {i}/{len(questions)}: {question['question']}")
        rows = execute_query(question["reference"]["sql"])
        question["ground_truth"] = rows
        print(f"  {len(rows)} rows")

    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    print(f"\nGround truth saved to: {QUESTIONS_FILE}")


if __name__ == "__main__":
    main()
