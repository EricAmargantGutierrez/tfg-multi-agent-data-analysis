import pytest

import src.orchestrator.router as router_mod
from src.orchestrator.router import keyword_route


# --- keyword_route: pure function, no LLM involved -----------------------

@pytest.mark.parametrize("question,expected", [
    ("How many orders are there?", "sql"),
    ("Create a bar chart of sales by region.", "viz"),
    ("Calculate the average profit.", "analysis"),
    ("Is there a correlation between discount and profit?", "analysis"),
    ("Generate the final report.", "report"),
])
def test_keyword_route_basic_cases(question, expected):
    assert keyword_route(question) == expected


def test_keyword_route_report_wins_over_analysis_keyword():
    """Regression test for the routing bug: a request that mentions BOTH
    a report and a statistical term must still go to 'report'."""
    q = "generate a report showing the average profit"
    assert keyword_route(q) == "report"


def test_keyword_route_report_wins_over_viz_keyword():
    q = "generate a report with a chart of last month"
    assert keyword_route(q) == "report"


# --- route(): LLM path + fallback, with build_llm stubbed ----------------

class _FakeResponse:
    def __init__(self, content):
        self.content = content


class _FakeLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, messages):
        return _FakeResponse(self._content)


class _RaisingLLM:
    def invoke(self, messages):
        raise RuntimeError("simulated LLM outage")


def test_route_uses_llm_decision_when_valid(monkeypatch):
    monkeypatch.setattr(router_mod, "build_llm", lambda: _FakeLLM('{"agent": "viz"}'))
    assert router_mod.route("some question") == "viz"


def test_route_falls_back_on_llm_outage(monkeypatch):
    monkeypatch.setattr(router_mod, "build_llm", lambda: _RaisingLLM())
    # Falls back to keyword_route, which should still get this right.
    assert router_mod.route("generate a report showing the average profit") == "report"


def test_route_falls_back_on_invalid_json(monkeypatch):
    monkeypatch.setattr(router_mod, "build_llm", lambda: _FakeLLM("not json"))
    assert router_mod.route("Create a bar chart of sales") == "viz"


def test_route_falls_back_on_unknown_agent_name(monkeypatch):
    monkeypatch.setattr(router_mod, "build_llm", lambda: _FakeLLM('{"agent": "weather"}'))
    assert router_mod.route("How many orders are there?") == "sql"
