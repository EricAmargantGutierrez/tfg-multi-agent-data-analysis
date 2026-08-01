import json
from pathlib import Path

from src.eval.checks import (
    check_analysis,
    check_chart_data,
    check_monolithic_analysis,
    check_monolithic_rows,
    check_sql,
    numbers_close,
    rows_match,
)

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


def test_check_monolithic_rows_handles_sql_shaped_output():
    answer = {"ok": True, "action": "sql", "rows": [["West", 725457.82]]}
    assert check_monolithic_rows(answer, [["West", 725457.8245]])


def test_check_monolithic_rows_handles_chart_shaped_output():
    # action="chart" returns list-of-dicts (sqlite3.Row), not list-of-lists
    answer = {"ok": True, "action": "chart", "rows": [{"region": "West", "total_sales": 725457.82}]}
    assert check_monolithic_rows(answer, [["West", 725457.8245]])


def test_check_monolithic_rows_rejects_wrong_data_regardless_of_action():
    answer = {"ok": True, "action": "sql", "rows": [["East", 1.0]]}
    assert not check_monolithic_rows(answer, [["West", 725457.8245]])


def test_check_monolithic_analysis_fails_gracefully_on_wrong_action():
    # picked action="sql" for a question that needed real statistics --
    # no "result" key in the expected shape, must fail cleanly not crash
    answer = {"ok": True, "action": "sql", "rows": [[33.85]]}
    gt = {"analysis": "correlation", "result": {"correlation": -0.22, "p_value": 0.001}}
    assert not check_monolithic_analysis(answer, gt)


# --- Baseline analysis: correlation/covariance/ttest are now genuinely
# checked, not auto-rejected -- regression/pca/kmeans remain auto-rejected
# since those really are infeasible in one plain SQL SELECT. ---

def test_baseline_analysis_scores_correct_correlation():
    from src.eval.checks import check_baseline_analysis
    answer = {"ok": True, "rows": [[-0.2195]]}
    gt = {"analysis": "correlation", "result": {"correlation": -0.2195, "p_value": 1e-100}}
    assert check_baseline_analysis(answer, gt)


def test_baseline_analysis_rejects_wrong_correlation():
    from src.eval.checks import check_baseline_analysis
    answer = {"ok": True, "rows": [[0.5]]}
    gt = {"analysis": "correlation", "result": {"correlation": -0.2195, "p_value": 1e-100}}
    assert not check_baseline_analysis(answer, gt)


def test_baseline_analysis_scores_correct_covariance():
    from src.eval.checks import check_baseline_analysis
    answer = {"ok": True, "rows": [[0.00396]]}
    gt = {"analysis": "covariance", "result": {"covariance": 0.00396}}
    assert check_baseline_analysis(answer, gt)


def test_baseline_analysis_scores_correct_ttest_via_t_statistic():
    from src.eval.checks import check_baseline_analysis
    answer = {"ok": True, "rows": [[-0.8556, 0.392]]}
    gt = {"analysis": "ttest", "result": {"t_statistic": -0.8556, "p_value": 0.392}}
    assert check_baseline_analysis(answer, gt)


def test_baseline_analysis_still_rejects_regression_pca_kmeans():
    from src.eval.checks import check_baseline_analysis
    for analysis_type, key_result in [
        ("regression", {"r2": 0.27}),
        ("pca", {"explained_variance_ratio": [0.5, 0.3, 0.2]}),
        ("kmeans", {"inertia": 1000.0}),
    ]:
        answer = {"ok": True, "rows": [[0.27]]}
        gt = {"analysis": analysis_type, "result": key_result}
        assert not check_baseline_analysis(answer, gt), f"{analysis_type} should remain auto-rejected"


def test_visualization_ground_truth_is_self_consistent():
    with open(DATASETS / "visualization_questions.json", encoding="utf-8") as f:
        questions = json.load(f)
    for q in questions:
        gt = q["ground_truth"]
        keys = ["col_" + str(i) for i in range(len(gt[0]))] if gt else []
        answer = {"ok": True, "rows": [dict(zip(keys, row)) for row in gt]}
        assert check_chart_data(answer, gt), f"Self-check failed for question {q['id']}"
