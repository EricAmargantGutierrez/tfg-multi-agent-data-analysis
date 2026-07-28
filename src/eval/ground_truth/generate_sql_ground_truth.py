from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.config.settings import settings


QUESTIONS_FILE = Path(__file__).parent / "evaluation_questions.json"


def execute_query(sql: str):

    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row

    try:

        rows = connection.execute(sql).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:

        connection.close()


def main():

    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    total = len(questions)

    print(f"Generating ground truth for {total} questions...\n")

    for i, question in enumerate(questions, start=1):

        print(f"Question {i}/{total}...")

        rows = execute_query(question["reference"]["sql"])

        normalized = [
            list(row.values())
            for row in rows
        ]

        question["ground_truth"] = normalized

    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:

        json.dump(
            questions,
            f,
            indent=4,
            ensure_ascii=False,
        )

    print()
    print("Ground truth successfully generated.")
    print(f"Saved to: {QUESTIONS_FILE}")


if __name__ == "__main__":
    main()