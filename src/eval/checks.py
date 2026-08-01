"""
src/eval/checks.py

Scoring logic. Every check here compares STRUCTURED output (rows, or a
result dict) against ground truth -- never narrated prose, since prose
can phrase the same correct answer many different ways.

Two deliberate simplifications, documented rather than hidden:
  - Numeric comparisons use a fixed absolute tolerance (rounding to 2
    decimal places by default), not true epsilon-based floating point
    comparison. Adequate for currency/count data at this scale; would
    need revisiting for a dataset with very small or very large values.
  - Row-set comparison for SQL/Viz splits each row into its numeric and
    non-numeric parts and compares each part as a sorted multiset. This
    makes the check robust to column reordering and row reordering
    without needing to know column semantics, but it can't tell apart
    two different numeric columns that happen to hold the same set of
    values in the same row shape. Acceptable for this benchmark's
    question set; would need real column-aware comparison for anything
    more adversarial.
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


def check_sql(answer: dict, ground_truth: list[list]) -> bool:
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
    # r2 is the headline metric; coefficients can wobble slightly more
    # than r2 under floating point without indicating a real error.
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
    "sql": check_sql,
    "visualization": check_chart_data,
    "analysis": check_analysis,
}


# ---------------------------------------------------------------------
# Baseline scoring: the baseline only ever returns {columns, rows} from a
# single bare SQL query, never a structured "analysis result". For SQL
# and Viz questions that shape already matches ground truth directly.
#
# For Analysis questions: this used to auto-reject anything outside
# {mean, count, min, max, ...} on the assumption a single SQL query
# structurally cannot express correlation/covariance/ttest. That
# assumption was WRONG -- evaluation showed a capable model deriving the
# correct closed-form Pearson correlation formula manually in raw SQL,
# matching the real system almost exactly, yet scored incorrect purely
# by this design, not because the math was wrong. Fixed: correlation,
# covariance, and (group-based) ttest are now genuinely checked against
# the key metric in the baseline's returned row. regression/pca/kmeans
# remain auto-rejected -- those genuinely require iterative optimization
# or matrix decomposition that a single, non-procedural SQL SELECT
# cannot express, which is a real structural limit, not an assumption.
# ---------------------------------------------------------------------
def check_baseline_sql_shaped(answer: dict, ground_truth: list[list]) -> bool:
    return check_sql(answer, ground_truth)


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

    # regression / pca / kmeans: genuinely infeasible in one plain SQL
    # SELECT -- this is the real finding, not an assumption.
    return False


BASELINE_CHECKERS = {
    "sql": check_baseline_sql_shaped,
    "visualization": check_baseline_sql_shaped,
    "analysis": check_baseline_analysis,
}


# ---------------------------------------------------------------------
# Monolithic baseline scoring: it can choose action="sql" (rows: list of
# lists) or action="chart" (rows: list of dicts, from sqlite3.Row) for
# the SAME question -- both are compared against the same list-of-lists
# ground truth SQL and Visualization questions already share (visualization
# ground truth is generated the same way SQL's is: raw rows from the
# reference SQL, not chart-specific). Normalizing here means the checker
# doesn't need to know or care which action the model picked; it only
# checks whether the underlying DATA is right, which is the actual
# question being scored either way.
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
    # If the model picked action="sql" instead of "analysis" for a
    # question that structurally needs real statistics, `answer` won't
    # have a "result" dict in the expected shape and this correctly (and
    # informatively) returns False -- a real finding: "chose the wrong
    # capability for this question", not a scorer bug.
    return check_analysis(answer, ground_truth)


MONOLITHIC_CHECKERS = {
    "sql": check_monolithic_rows,
    "visualization": check_monolithic_rows,
    "analysis": check_monolithic_analysis,
}
