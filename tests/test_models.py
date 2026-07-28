import pytest
from pydantic import ValidationError

from src.core.db import build_select
from src.models.schemas import AnalysisPlan, ChartSpec, Filter, RoutingDecision

VALID_COLS = {"region", "sales", "profit", "order_date", "category"}


# --- Filter / AnalysisPlan validation -----------------------------------

def test_filter_equality_ok():
    f = Filter(column="region", op="=", value="West")
    assert f.value == "West"


def test_filter_in_requires_nonempty_list():
    with pytest.raises(ValidationError):
        Filter(column="region", op="IN", value=[])
    with pytest.raises(ValidationError):
        Filter(column="region", op="IN", value="West")  # not a list


def test_filter_between_requires_two_elements():
    with pytest.raises(ValidationError):
        Filter(column="order_date", op="BETWEEN", value=["2018-01-01"])
    f = Filter(column="order_date", op="BETWEEN", value=["2018-01-01", "2018-12-31"])
    assert len(f.value) == 2


def test_analysis_plan_normalizes_column_names():
    plan = AnalysisPlan(analysis="mean", columns=["Profit Margin"], filters=[])
    assert plan.columns == ["profit_margin"]


def test_analysis_plan_requires_at_least_one_column():
    with pytest.raises(ValidationError):
        AnalysisPlan(analysis="mean", columns=[], filters=[])


# --- ChartSpec / RoutingDecision -----------------------------------------

def test_chart_spec_rejects_unsupported_type():
    with pytest.raises(ValidationError):
        ChartSpec(chart_type="pyramid", sql="SELECT 1")


def test_routing_decision_rejects_unknown_agent():
    with pytest.raises(ValidationError):
        RoutingDecision(agent="weather")


# --- build_select: this is the actual bug fix -----------------------------

def test_build_select_no_filters():
    sql, params = build_select(columns=["profit"], filters=[], valid_columns=VALID_COLS)
    assert "WHERE" not in sql
    assert params == []


def test_build_select_equality_filter_is_parameterized():
    sql, params = build_select(
        columns=["profit"],
        filters=[{"column": "region", "op": "=", "value": "West"}],
        valid_columns=VALID_COLS,
    )
    assert "WHERE region = ?" in sql
    assert params == ["West"]
    # the value must never be interpolated into the SQL text itself
    assert "West" not in sql


def test_build_select_like_filter_for_year():
    sql, params = build_select(
        columns=["sales"],
        filters=[{"column": "order_date", "op": "LIKE", "value": "2018-%"}],
        valid_columns=VALID_COLS,
    )
    assert "order_date LIKE ?" in sql
    assert params == ["2018-%"]


def test_build_select_between_filter():
    sql, params = build_select(
        columns=["sales"],
        filters=[{"column": "order_date", "op": "BETWEEN", "value": ["2018-01-01", "2018-06-30"]}],
        valid_columns=VALID_COLS,
    )
    assert "order_date BETWEEN ? AND ?" in sql
    assert params == ["2018-01-01", "2018-06-30"]


def test_build_select_in_filter():
    sql, params = build_select(
        columns=["sales"],
        filters=[{"column": "region", "op": "IN", "value": ["West", "East"]}],
        valid_columns=VALID_COLS,
    )
    assert "region IN (?, ?)" in sql
    assert params == ["West", "East"]


def test_build_select_rejects_unknown_column():
    with pytest.raises(ValueError):
        build_select(columns=["not_a_real_column"], filters=[], valid_columns=VALID_COLS)


def test_build_select_rejects_unknown_filter_column():
    with pytest.raises(ValueError):
        build_select(
            columns=["profit"],
            filters=[{"column": "not_a_real_column", "op": "=", "value": 1}],
            valid_columns=VALID_COLS,
        )
