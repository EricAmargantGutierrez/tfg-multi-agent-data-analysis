import src.orchestrator.narrate as narrate_mod
from src.orchestrator.narrate import narrate


class _ExplodingLLM:
    """If narrate() ever calls build_llm() for a path that shouldn't need
    an LLM, this makes the test fail loudly instead of silently."""
    def invoke(self, messages):
        raise AssertionError("narrate() should not call the LLM for this path")


def test_error_result_returns_error_without_calling_llm(monkeypatch):
    monkeypatch.setattr(narrate_mod, "build_llm", lambda: _ExplodingLLM())
    result = {"ok": False, "error": "something broke"}
    assert narrate("q", "sql", result) == "something broke"


def test_report_result_formats_path_without_calling_llm(monkeypatch):
    monkeypatch.setattr(narrate_mod, "build_llm", lambda: _ExplodingLLM())
    result = {"ok": True, "answer": {"path": "/tmp/report.md"}}
    text = narrate("q", "report", result)
    assert "/tmp/report.md" in text


def test_report_result_missing_path_does_not_crash(monkeypatch):
    monkeypatch.setattr(narrate_mod, "build_llm", lambda: _ExplodingLLM())
    result = {"ok": True, "answer": {}}
    text = narrate("q", "report", result)
    assert "unknown location" in text


def test_success_result_uses_llm(monkeypatch):
    class _FakeLLM:
        def invoke(self, messages):
            class R:
                content = "The West region led."
            return R()

    monkeypatch.setattr(narrate_mod, "build_llm", lambda: _FakeLLM())
    result = {"ok": True, "columns": ["region"], "rows": [["West"]]}
    assert narrate("q", "sql", result) == "The West region led."
