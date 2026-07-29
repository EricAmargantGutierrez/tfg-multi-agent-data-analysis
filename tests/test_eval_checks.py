import json
from pathlib import Path

from src.eval.checks import check_analysis, check_chart_data, check_sql, numbers_close, rows_match

DATASETS = Path(__file__).resolve().parents[1] / "src" / "eval" / "datasets"


# --- numbers_close / rows_match -------------------------------------------

def test_numbers_close_within_tolerance():
    assert numbers_close(33.849, 33.85)
    assert not numbers_close(33.0, 33.85)


def test_rows_match_ignores_row_order():
    a = [["West", 100], ["East", 50]]
    b = [["East", 50], ["West", 100]]
    assert rows_match(a, b)


def test_rows_match_ignores_column_order():
    a = [["West", 100]]
    b = [[100, "West"]]
    assert rows_match(a, b)


def test_rows_match_tolerates_float_noise():
    a = [["West", 100.001]]
    b = [["West", 100.0]]
    assert rows_match(a, b)


def test_rows_match_rejects_wrong_value():
    a = [["West", 999]]
    b = [["West", 100]]
    assert not rows_match(a, b)


def test_rows_match_rejects_different_row_count():
    assert not rows_match([["West", 1]], [["West", 1], ["East", 2]])


# --- check_sql / check_chart_data -----------------------------------------

def test_check_sql_ok():
    answer = {"ok": True, "rows": [["West", 725457.82]]}
    assert check_sql(answer, [["West", 725457.8245]])


def test_check_sql_fails_when_not_ok():
    answer = {"ok": False, "rows": [["West", 725457.82]]}
    assert not check_sql(answer, [["West", 725457.8245]])


def test_check_chart_data_ok():
    answer = {"ok": True, "rows": [{"category": "Furniture", "total_sales": 500.0}]}
    assert check_chart_data(answer, [["Furniture", 500.0]])


# --- check_analysis: synthetic cases per type ------------------------------

def test_check_analysis_scalar_ok():
    answer = {"ok": True, "result": {"analysis": "mean", "result": 33.849}}
    gt = {"analysis": "mean", "result": 33.85}
    assert check_analysis(answer, gt)


def test_check_analysis_scalar_wrong():
    answer = {"ok": True, "result": {"analysis": "mean", "result": 28.66}}
    gt = {"analysis": "mean", "result": 33.85}
    assert not check_analysis(answer, gt)


def test_check_analysis_dict_result_ok():
    answer = {"ok": True, "result": {"analysis": "correlation", "result": {"correlation": -0.219, "p_value": 0.0003}}}
    gt = {"analysis": "correlation", "result": {"correlation": -0.22, "p_value": 0.0004}}
    assert check_analysis(answer, gt)


def test_check_analysis_mismatched_type_fails():
    answer = {"ok": True, "result": {"analysis": "median", "result": 33.85}}
    gt = {"analysis": "mean", "result": 33.85}
    assert not check_analysis(answer, gt)


def test_check_analysis_pca_ok():
    answer = {"ok": True, "result": {"analysis": "pca", "result": {"explained_variance_ratio": [0.51, 0.30, 0.19]}}}
    gt = {"analysis": "pca", "result": {"explained_variance_ratio": [0.50, 0.31, 0.19]}}
    assert check_analysis(answer, gt)


def test_check_analysis_not_ok_fails():
    answer = {"ok": False, "result": None}
    gt = {"analysis": "mean", "result": 33.85}
    assert not check_analysis(answer, gt)


# --- Meta-test: real generated ground truth must pass against itself ------

def test_sql_ground_truth_is_self_consistent():
    """If the generator produced ground_truth, running check_sql with the
    exact same rows as the 'answer' must return True. Not a tautology --
    this catches bugs in the checker's shape-handling against real data."""
    with open(DATASETS / "sql_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        gt = q["ground_truth"]
        answer = {"ok": True, "rows": gt}
        assert check_sql(answer, gt), f"Self-check failed for question {q['id']}"


def test_analysis_ground_truth_is_self_consistent():
    with open(DATASETS / "analysis_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        gt = q["ground_truth"]
        if gt is None:
            continue
        answer = {"ok": True, "result": gt}
        assert check_analysis(answer, gt), f"Self-check failed for question {q['id']}"


def test_visualization_ground_truth_is_self_consistent():
    with open(DATASETS / "visualization_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        gt = q["ground_truth"]
        keys = ["col_" + str(i) for i in range(len(gt[0]))] if gt else []
        answer = {"ok": True, "rows": [dict(zip(keys, row)) for row in gt]}
        assert check_chart_data(answer, gt), f"Self-check failed for question {q['id']}"
