"""
src/eval/ground_truth/generate_sql_ground_truth.py

Executes each question's hand-written reference SQL against the real
database and stores the actual result as ground_truth. No LLM involved --
this is what makes it trustworthy as a scoring baseline.

Run once, after `python -m src.ingest`, and whenever the dataset changes:
    python -m src.eval.ground_truth.generate_sql_ground_truth
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.config.settings import settings

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "datasets" / "sql_questions.json"


def execute_query(sql: str) -> list[list]:
    connection = sqlite3.connect(settings.database_path)
    try:
        rows = connection.execute(sql).fetchall()
        return [list(row) for row in rows]
    finally:
        connection.close()


def main() -> None:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Generating ground truth for {len(questions)} SQL questions...\n")

    for i, question in enumerate(questions, start=1):
        print(f"Question {i}/{len(questions)}: {question['question']}")
        rows = execute_query(question["reference"]["sql"])
        question["ground_truth"] = rows

    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    print(f"\nGround truth saved to: {QUESTIONS_FILE}")


if __name__ == "__main__":
    main()
