from src.eval.utils.warmup import warm_up, warm_up_model


def test_warm_up_calls_the_given_function(capsys):
    calls = []
    def fake_fn(question):
        calls.append(question)
        return {"ok": True}

    warm_up(fake_fn, question="test question")

    assert calls == ["test question"]
    captured = capsys.readouterr()
    assert "warm-up took" in captured.out


def test_warm_up_passes_model_key_when_given():
    calls = []
    def fake_fn(question, model_key=None):
        calls.append((question, model_key))
        return {"ok": True}

    warm_up(fake_fn, model_key="ollama")
    assert calls == [("How many orders are there?", "ollama")]


def test_warm_up_swallows_exceptions(capsys):
    def failing_fn(question):
        raise RuntimeError("simulated failure")

    warm_up(failing_fn)  # must not raise
    captured = capsys.readouterr()
    assert "ignoring" in captured.out


def test_warm_up_works_with_a_lambda_wrapping_a_different_signature():
    # e.g. wrapping graph.answer(question, history) to match warm_up's
    # single-argument call convention, as pipeline_benchmark.py does
    calls = []
    def answer(question, history):
        calls.append((question, history))
        return {"ok": True}

    warm_up(lambda q: answer(q, []))
    assert calls == [("How many orders are there?", [])]


def test_warm_up_model_backcompat_wrapper(monkeypatch, capsys):
    import src.agents.sql.engine as sql_engine_mod
    monkeypatch.setattr(sql_engine_mod, "run_sql_core", lambda q, model_key=None: {"ok": True})

    warm_up_model()  # must not raise, must warm up via run_sql_core internally
    captured = capsys.readouterr()
    assert "warm-up took" in captured.out
