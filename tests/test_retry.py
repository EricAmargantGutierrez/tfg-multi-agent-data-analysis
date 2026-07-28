from src.core.retry import run_self_correcting


def test_succeeds_first_try():
    def step(error_context):
        assert error_context is None
        return {"value": 42}

    result = run_self_correcting(step, max_retries=3)
    assert result["ok"] is True
    assert result["attempts"] == 1
    assert result["retried"] is False
    assert result["value"] == 42


def test_retries_then_succeeds():
    calls = []

    def step(error_context):
        calls.append(error_context)
        if len(calls) < 2:
            raise ValueError("simulated failure")
        return {"value": "recovered"}

    result = run_self_correcting(step, max_retries=3)
    assert result["ok"] is True
    assert result["attempts"] == 2
    assert result["retried"] is True
    assert calls[0] is None
    assert "simulated failure" in calls[1]


def test_exhausts_retries_and_returns_failure_defaults():
    def step(error_context):
        raise ValueError("always fails")

    result = run_self_correcting(
        step, max_retries=3, failure_defaults={"columns": [], "rows": [], "sql": None}
    )
    assert result["ok"] is False
    assert result["attempts"] == 3
    assert result["retried"] is True
    assert "always fails" in result["error"]
    assert result["columns"] == []
    assert result["sql"] is None
