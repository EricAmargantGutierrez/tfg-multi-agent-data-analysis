"""
src/eval/checks.py

Scoring logic. Compares structured output (rows, or a result dict)
against ground truth - never the narrated text, since the same correct
answer can be worded many ways.

Two deliberate simplifications:
  - Numbers are compared with a fixed tolerance (2 decimals), not real
    float epsilon. Fine at this scale, but wouldn't hold for a dataset
    with much smaller/bigger numbers.
  - Row comparison ignores column/row order by splitting each row into
    a set of numbers and a set of strings. Can't tell apart two numeric
    columns with the same values - not an issue for this question set.
"""
from __future__ import annotations

from typing import Any

TOL = 0.01  # absolute tolerance for numeric comparisons


def _is_number(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def numbers_close(a: float, b: float, tol: float = TOL) -> bool:
    return abs(a - b) <= tol


def _normalize_row(row: list) -> tuple:
    nums = tuple(sorted(round(float(v), 2) for v in row if _is_number(v)))
    strs = tuple(sorted(str(v) for v in row if not _is_number(v)))
    return (strs, nums)


def rows_match(actual: list[list], expected: list[list]) -> bool:
    """Order-independent, column-order-independent row comparison."""
    if actual is None or expected is None:
        return False
    if len(actual) != len(expected):
        return False
    return sorted(_normalize_row(r) for r in actual) == sorted(_normalize_row(r) for r in expected)


def check_data_query(answer: dict, ground_truth: list[list]) -> bool:
    if not answer.get("ok"):
        return False
    return rows_match(answer.get("rows"), ground_truth)


def check_chart_data(answer: dict, ground_truth: list[list]) -> bool:
    """Same principle as SQL: check the DATA the chart was built from,
    never the rendered PNG."""
    if not answer.get("ok"):
        return False
    rows = answer.get("rows")
    if not rows:
        return False
    # rows is a list[dict] for the viz agent; normalize to list[list]
    row_lists = [list(r.values()) for r in rows]
    return rows_match(row_lists, ground_truth)


# ---------------------------------------------------------------------
# Analysis: different shape per analysis type, so dispatch per type.
# ---------------------------------------------------------------------
_SCALAR_TYPES = {"mean", "median", "mode", "min", "max", "variance", "std", "count"}
_DICT_TYPES = {"correlation", "covariance", "ttest"}


def _check_scalar(actual: dict, expected: dict) -> bool:
    a, e = actual.get("result"), expected.get("result")
    if a is None or e is None:
        return False
    return numbers_close(a, e)


def _check_dict_result(actual: dict, expected: dict) -> bool:
    a, e = actual.get("result"), expected.get("result")
    if not isinstance(a, dict) or not isinstance(e, dict):
        return False
    for key, e_val in e.items():
        a_val = a.get(key)
        if a_val is None:
            return False
        if _is_number(e_val):
            if not numbers_close(a_val, e_val):
                return False
        elif a_val != e_val:
            return False
    return True


def _check_regression(actual: dict, expected: dict) -> bool:
    a, e = actual.get("result"), expected.get("result")
    if not isinstance(a, dict) or not isinstance(e, dict):
        return False
    # r2 is the number that matters; coefficients drift more from
    # floating point without being wrong.
    return numbers_close(a.get("r2", -999), e.get("r2", -999), tol=0.02)


def _check_pca(actual: dict, expected: dict) -> bool:
    a, e = actual.get("result"), expected.get("result")
    if not isinstance(a, dict) or not isinstance(e, dict):
        return False
    a_ratios = a.get("explained_variance_ratio")
    e_ratios = e.get("explained_variance_ratio")
    if not a_ratios or not e_ratios or len(a_ratios) != len(e_ratios):
        return False
    return all(numbers_close(x, y, tol=0.02) for x, y in zip(a_ratios, e_ratios))


def _check_kmeans(actual: dict, expected: dict) -> bool:
    a, e = actual.get("result"), expected.get("result")
    if not isinstance(a, dict) or not isinstance(e, dict):
        return False
    return numbers_close(a.get("inertia", -1), e.get("inertia", -1), tol=max(1.0, abs(e.get("inertia", 0)) * 0.05))


def check_analysis(answer: dict, ground_truth: dict) -> bool:
    if not answer.get("ok") or ground_truth is None:
        return False

    analysis_type = ground_truth.get("analysis")
    actual_result = answer.get("result")
    if actual_result is None or actual_result.get("analysis") != analysis_type:
        return False

    if analysis_type in _SCALAR_TYPES:
        return _check_scalar(actual_result, ground_truth)
    if analysis_type in _DICT_TYPES:
        return _check_dict_result(actual_result, ground_truth)
    if analysis_type == "regression":
        return _check_regression(actual_result, ground_truth)
    if analysis_type == "pca":
        return _check_pca(actual_result, ground_truth)
    if analysis_type == "kmeans":
        return _check_kmeans(actual_result, ground_truth)

    return False


CHECKERS = {
    "data_query": check_data_query,
    "visualization": check_chart_data,
    "analysis": check_analysis,
}


# ---------------------------------------------------------------------
# Baseline scoring: the baseline only ever returns {columns, rows} from
# one plain SQL query, which already matches Data Query/Viz ground truth.
#
# For Analysis questions, correlation/covariance/ttest ARE checked (a
# model can derive these by hand in SQL - testing showed one doing so
# correctly). Regression/PCA/K-Means are auto-failed: those genuinely
# need iterative optimization or matrix math a single SELECT can't do.
# ---------------------------------------------------------------------
def check_baseline_sql_shaped(answer: dict, ground_truth: list[list]) -> bool:
    return check_data_query(answer, ground_truth)


_BASELINE_STRUCTURALLY_IMPOSSIBLE = {"regression", "pca", "kmeans"}
_BASELINE_DICT_KEY = {"correlation": "correlation", "covariance": "covariance", "ttest": "t_statistic"}


def check_baseline_analysis(answer: dict, ground_truth: dict) -> bool:
    if not answer.get("ok") or ground_truth is None:
        return False
    analysis_type = ground_truth.get("analysis")

    rows = answer.get("rows")
    if not rows or not rows[0]:
        return False
    candidates = [v for v in rows[0] if _is_number(v)]
    if not candidates:
        return False

    if analysis_type in _SCALAR_TYPES:
        expected = ground_truth.get("result")
        if not _is_number(expected):
            return False
        return any(numbers_close(c, expected) for c in candidates)

    if analysis_type in _DICT_TYPES:
        key = _BASELINE_DICT_KEY.get(analysis_type)
        expected = ground_truth.get("result", {}).get(key) if key else None
        if not _is_number(expected):
            return False
        return any(numbers_close(c, expected) for c in candidates)

    # regression / pca / kmeans: can't be done in one plain SQL SELECT.
    return False


BASELINE_CHECKERS = {
    "data_query": check_baseline_sql_shaped,
    "visualization": check_baseline_sql_shaped,
    "analysis": check_baseline_analysis,
}


# ---------------------------------------------------------------------
# Monolithic baseline: for the same question it might pick action="sql"
# (list of lists) or action="chart" (list of dicts). Normalize both to
# the same shape so the checker only cares whether the data is right,
# not which action the model picked.
# ---------------------------------------------------------------------
def check_monolithic_rows(answer: dict, ground_truth: list[list]) -> bool:
    if not answer.get("ok"):
        return False
    rows = answer.get("rows")
    if not rows:
        return False
    row_lists = [list(r.values()) for r in rows] if isinstance(rows[0], dict) else rows
    return rows_match(row_lists, ground_truth)


def check_monolithic_analysis(answer: dict, ground_truth: dict) -> bool:
    # If the model picked action="sql" for a question needing real
    # statistics, `answer` won't have a "result" dict and this correctly
    # fails - a real finding, not a checker bug.
    return check_analysis(answer, ground_truth)


MONOLITHIC_CHECKERS = {
    "data_query": check_monolithic_rows,
    "visualization": check_monolithic_rows,
    "analysis": check_monolithic_analysis,
}
