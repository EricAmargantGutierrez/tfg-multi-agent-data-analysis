"""
src/eval/ground_truth/generate_visualization_ground_truth.py

Runs each question's hand-written reference SQL and stores the result as
ground_truth. A chart is checked against the DATA it was built from,
never the rendered PNG - same idea as the Viz Agent itself.

Run once, after `python -m src.ingest`, and again whenever the dataset
changes:
    python -m src.eval.ground_truth.generate_visualization_ground_truth
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.config.settings import settings
from src.eval.languages import question_text
from src.core.db import MAX_ROWS

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "datasets" / "visualization_questions.json"


def execute_query(sql: str) -> list[list]:
    connection = sqlite3.connect(settings.database_path)
    try:
        cursor = connection.execute(sql)
        # Capped the same as run_readonly_query_dicts (what the real Viz
        # Agent uses) -- otherwise ground truth wouldn't match what the
        # agent can actually return for a chart over MAX_ROWS points.
        rows = cursor.fetchmany(MAX_ROWS)
        return [list(row) for row in rows]
    finally:
        connection.close()


def main() -> None:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Generating ground truth for {len(questions)} visualization questions...\n")

    for i, question in enumerate(questions, start=1):
        print(f"Question {i}/{len(questions)}: {question_text(question)}")
        rows = execute_query(question["reference"]["sql"])
        question["ground_truth"] = rows
        print(f"  {len(rows)} rows")

    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    print(f"\nGround truth saved to: {QUESTIONS_FILE}")


if __name__ == "__main__":
    main()
