"""
src/eval/ground_truth/generate_analysis_ground_truth.py

For each question, executes its hand-written reference plan (analysis +
columns + filters -- the SAME shape the real AnalysisPlan uses) through
the real, already-tested `src/core/db.py` and
`src/agents/analysis/statistics.py` code. No LLM is involved in computing
ground truth: the plan was written by a human when the question was
authored, exactly the way generate_sql_ground_truth.py uses a
human-written reference SQL rather than asking an LLM what the "right"
query is.

Run once, after `python -m src.ingest`, and whenever the dataset changes:
    python -m src.eval.ground_truth.generate_analysis_ground_truth
"""
from __future__ import annotations

import json
from pathlib import Path

from src.agents.analysis.statistics import ANALYSIS_FUNCTIONS
from src.core.db import build_select, get_valid_columns, load_dataframe_readonly

QUESTIONS_FILE = Path(__file__).resolve().parents[1] / "datasets" / "analysis_questions.json"


def compute_ground_truth(reference: dict) -> dict:
    valid_columns = get_valid_columns()

    columns = list(reference["columns"])
    target = reference.get("target")
    if target and target not in columns:
        columns = [*columns, target]

    sql, params = build_select(
        columns=columns,
        filters=reference.get("filters", []),
        valid_columns=valid_columns,
    )
    df = load_dataframe_readonly(sql, params)
    function = ANALYSIS_FUNCTIONS[reference["analysis"]]
    if reference["analysis"] == "regression":
        return function(df, target=target)
    return function(df)


def main() -> None:
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        questions = json.load(f)

    print(f"Generating ground truth for {len(questions)} analysis questions...\n")

    for i, question in enumerate(questions, start=1):
        print(f"Question {i}/{len(questions)}: {question['question']}")
        try:
            result = compute_ground_truth(question["reference"])
            question["ground_truth"] = result
        except Exception as e:
            print(f"  FAILED: {e}")
            question["ground_truth"] = None

    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=4, ensure_ascii=False)

    failed = [q["id"] for q in questions if q.get("ground_truth") is None]
    if failed:
        print(f"\nWARNING: ground truth generation failed for question ids: {failed}")
    print(f"\nGround truth saved to: {QUESTIONS_FILE}")


if __name__ == "__main__":
    main()
