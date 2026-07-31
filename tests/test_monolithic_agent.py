"""
Tests the monolithic agent's action dispatch and self-correction against
the REAL project database (data/superstore.db) -- core.db's functions
bind their db_path default at import time, so patching it after the fact
doesn't reach already-defined function signatures; testing against the
real DB with dynamically-computed expected values sidesteps that
entirely and is more representative anyway.

Requires data/superstore.db to exist (run `python -m src.ingest` first).
"""
import json
import sqlite3

import pytest

from src.config.settings import settings
from src.eval.baselines.monolithic_agent import run_monolithic_agent

pytestmark = pytest.mark.skipif(
    not settings.database_path.exists(),
    reason="requires data/superstore.db -- run `python -m src.ingest` first",
)


def _real_db_value(sql):
    con = sqlite3.connect(settings.database_path)
    try:
        return con.execute(sql).fetchone()[0]
    finally:
        con.close()


class _FakeResponse:
    def __init__(self, content): self.content = content


class _ScriptedLLM:
    """Returns each response in order, one per .invoke() call -- lets a
    test simulate a bad first attempt followed by a corrected retry."""
    def __init__(self, responses):
        self.responses = list(responses)

    def invoke(self, messages):
        return _FakeResponse(self.responses.pop(0))


def test_sql_action_executes_real_query(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        ['{"action": "sql", "sql": "SELECT COUNT(*) AS n FROM orders"}']
    ))
    result = run_monolithic_agent("How many orders are there?")
    expected = _real_db_value("SELECT COUNT(*) FROM orders")
    assert result["ok"] is True
    assert result["action"] == "sql"
    assert result["rows"] == [[expected]]


def test_analysis_action_executes_real_stats(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        [json.dumps({"action": "analysis", "analysis": "mean", "columns": ["profit"], "filters": []})]
    ))
    result = run_monolithic_agent("What is the average profit?")
    expected = _real_db_value("SELECT AVG(profit) FROM orders")
    assert result["ok"] is True
    assert result["action"] == "analysis"
    assert result["result"]["result"] == pytest.approx(expected, rel=1e-4)


def test_analysis_action_with_filter(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        [json.dumps({
            "action": "analysis", "analysis": "mean", "columns": ["profit"],
            "filters": [{"column": "region", "op": "=", "value": "West"}],
        })]
    ))
    result = run_monolithic_agent("What is the average profit in the West region?")
    expected = _real_db_value("SELECT AVG(profit) FROM orders WHERE region = 'West'")
    assert result["ok"] is True
    assert result["result"]["result"] == pytest.approx(expected, rel=1e-4)


def test_regression_requires_target_like_the_real_agent(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    # first attempt forgets "target" -- should be rejected and retried
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM([
        json.dumps({"action": "analysis", "analysis": "regression",
                    "columns": ["sales", "discount"], "filters": []}),
        json.dumps({"action": "analysis", "analysis": "regression",
                    "columns": ["sales", "discount"], "target": "profit", "filters": []}),
    ]))
    result = run_monolithic_agent("Predict profit from sales and discount.")
    assert result["ok"] is True
    assert result["retried"] is True
    assert result["result"]["result"]["target"] == "profit"


def test_chart_action_executes_and_renders(monkeypatch, tmp_path):
    import src.eval.baselines.monolithic_agent as mod
    import src.agents.viz.engine as viz_mod
    monkeypatch.setattr(viz_mod, "RESULTS_DIR", tmp_path)
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        [json.dumps({
            "action": "chart", "chart_type": "bar",
            "sql": "SELECT region, SUM(sales) AS total_sales FROM orders GROUP BY region",
        })]
    ))
    result = run_monolithic_agent("Show a bar chart of sales by region.")
    expected_groups = _real_db_value("SELECT COUNT(*) FROM (SELECT region FROM orders GROUP BY region)")
    assert result["ok"] is True
    assert result["action"] == "chart"
    assert len(result["rows"]) == expected_groups


def test_unknown_action_triggers_retry_then_failure(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        ['{"action": "make_coffee"}'] * 3
    ))
    result = run_monolithic_agent("Nonsense question.", max_retries=3)
    assert result["ok"] is False
    assert result["attempts"] == 3


def test_invalid_sql_is_rejected_by_the_real_safety_guard(monkeypatch):
    import src.eval.baselines.monolithic_agent as mod
    monkeypatch.setattr(mod, "build_llm", lambda model_key=None: _ScriptedLLM(
        ['{"action": "sql", "sql": "DROP TABLE orders"}'] * 3
    ))
    result = run_monolithic_agent("Malicious question.", max_retries=3)
    assert result["ok"] is False
