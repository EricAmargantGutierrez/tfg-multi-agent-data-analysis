from src.agents.report.engine import generate_report_core


def test_report_prompt_is_summarized_for_large_row_history(monkeypatch, tmp_path):
    """Reproduces the real failure: a session including a boxplot/scatter
    result (hundreds of rows) blew a single report-generation request
    up to ~14,700 tokens, because json.dumps(history) embedded the full
    raw rows list for every turn."""
    captured_prompt = {}

    class _CapturingLLM:
        def invoke(self, messages):
            captured_prompt["text"] = messages[1]["content"]
            class R:
                content = "# Executive Summary\n\nTest report."
            return R()

    import src.agents.report.engine as engine_mod
    monkeypatch.setattr(engine_mod, "build_llm", lambda: _CapturingLLM())
    monkeypatch.setattr(engine_mod, "RESULTS_DIR", tmp_path)

    big_rows = [{"profit": i / 10} for i in range(800)]  # a realistic boxplot-sized result
    history = [
        {"question": "How many orders are there?", "agent": "sql",
         "result": {"ok": True, "columns": ["total"], "rows": [[9994]], "sql": "SELECT COUNT(*)..."}},
        {"question": "Show a boxplot of profit", "agent": "viz",
         "result": {"ok": True, "path": "/tmp/chart.png", "rows": big_rows,
                    "spec": {"chart_type": "boxplot"}}},
    ]

    result = generate_report_core(history)

    assert result["ok"] is True
    assert "800" in captured_prompt["text"]  # row count still mentioned
    assert len(captured_prompt["text"]) < 3000  # not the full 800 rows dumped raw
