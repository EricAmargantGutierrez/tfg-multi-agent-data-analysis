from src.core.summarize import MAX_ROWS_IN_PROMPT, SAMPLE_ROWS_SHOWN, summarize_large_rows


def test_leaves_small_row_lists_untouched():
    result = {"ok": True, "rows": [{"x": 1, "y": 2}, {"x": 3, "y": 4}]}
    assert summarize_large_rows(result) == result


def test_truncates_large_dict_row_lists():
    big_rows = [{"discount": i, "profit": i * 2} for i in range(1000)]
    result = {"ok": True, "path": "/tmp/chart.png", "rows": big_rows}
    summarized = summarize_large_rows(result)

    assert summarized["rows"]["total_rows"] == 1000
    assert len(summarized["rows"]["sample_first_rows"]) == SAMPLE_ROWS_SHOWN
    assert summarized["path"] == "/tmp/chart.png"  # other fields untouched


def test_truncates_large_list_of_lists_too():
    # SQL Agent rows are list-of-lists, not list-of-dicts
    big_rows = [[i, i * 2] for i in range(500)]
    result = {"ok": True, "rows": big_rows}
    summarized = summarize_large_rows(result)
    assert summarized["rows"]["total_rows"] == 500


def test_does_not_touch_short_numeric_lists():
    # regression coefficients, PCA explained_variance_ratio, etc. -- short
    # lists of plain floats, not row-shaped data, must pass through
    result = {"coefficients": [0.18, -233.4, -2.96], "explained_variance_ratio": [0.5, 0.3, 0.2]}
    assert summarize_large_rows(result) == result


def test_recurses_into_nested_history_structure():
    # This is the actual shape used by report_agent/engine.py: a list of
    # turns, each with a nested "result" dict that may itself have rows.
    big_rows = [{"x": i} for i in range(50)]
    history = [
        {"question": "q1", "agent": "sql", "result": {"ok": True, "rows": [["a", 1]]}},
        {"question": "q2", "agent": "viz", "result": {"ok": True, "rows": big_rows}},
    ]
    summarized = summarize_large_rows(history)

    assert summarized[0]["result"]["rows"] == [["a", 1]]  # small, untouched
    assert summarized[1]["result"]["rows"]["total_rows"] == 50  # large, summarized


def test_exactly_at_threshold_is_untouched():
    rows = [{"x": i} for i in range(MAX_ROWS_IN_PROMPT)]
    result = {"rows": rows}
    assert summarize_large_rows(result)["rows"] == rows


def test_one_over_threshold_is_summarized():
    rows = [{"x": i} for i in range(MAX_ROWS_IN_PROMPT + 1)]
    result = {"rows": rows}
    summarized = summarize_large_rows(result)
    assert isinstance(summarized["rows"], dict)
    assert summarized["rows"]["total_rows"] == MAX_ROWS_IN_PROMPT + 1
