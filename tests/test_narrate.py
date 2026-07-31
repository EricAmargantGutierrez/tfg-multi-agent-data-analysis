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


# --- Regression tests: large row lists must never be dumped raw into the
# prompt. Reproduces the actual failure observed in production: a 1000-row
# Viz Agent scatter result triggered a 413 "Request too large" error
# because the full raw rows list was being embedded in the prompt text.
# The fix itself (summarize_large_rows) is unit-tested in
# tests/test_summarize.py; these tests confirm narrate() actually uses it. ---

def test_narrate_with_1000_row_result_does_not_blow_up_the_prompt(monkeypatch):
    captured_prompt = {}

    class _CapturingLLM:
        def invoke(self, messages):
            captured_prompt["text"] = messages[1]["content"]
            class R:
                content = "A scatter plot was generated."
            return R()

    monkeypatch.setattr(narrate_mod, "build_llm", lambda: _CapturingLLM())
    big_rows = [{"discount": i / 1000, "profit": i * 2.5} for i in range(1000)]
    result = {"ok": True, "path": "/tmp/chart.png", "rows": big_rows, "spec": {"chart_type": "scatter"}}

    narrate("Show a scatter plot", "viz", result)

    # The prompt must reference the row count, not contain all 1000 rows
    # verbatim -- a rough proxy: the raw dict repr of 1000 rows would be
    # tens of thousands of characters; the summarized version should be
    # a small fraction of that.
    assert "1000" in captured_prompt["text"]
    assert len(captured_prompt["text"]) < 3000
