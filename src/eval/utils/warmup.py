"""
src/eval/utils/warmup.py

Makes one throwaway call through the exact same code path as the real
timed calls, before any real timing starts. Matters most for local
models (Ollama), where the first call of a given kind pays a large
cold-start cost (~90-180s) that a trivial "Say OK" call doesn't cover.

There's no single "the model is warm now" -- each different function/
code path needs its own warm-up, right before its own timed loop.
"""
import time


def warm_up(call_fn, question: str = "How many orders are there?", model_key: str | None = None) -> None:
    """call_fn: any callable taking a question string (optionally a
    model_key kwarg). Failures are swallowed -- a warm-up call exists
    to pay a cost, not to be scored."""
    print(f"Warming up ({getattr(call_fn, '__name__', 'call')})...")
    start = time.perf_counter()
    try:
        if model_key is not None:
            call_fn(question, model_key=model_key)
        else:
            call_fn(question)
    except Exception as e:
        print(f"  (warm-up call raised {type(e).__name__}, ignoring -- it's throwaway)")
    elapsed = time.perf_counter() - start
    print(f"  warm-up took {elapsed:.1f}s\n")


def warm_up_model(model_key: str | None = None) -> None:
    """Back-compat convenience: warms up via the Data Query Agent. Prefer
    warm_up(your_actual_function) when the timed loop uses a different one."""
    from src.agents.data_query.engine import run_data_query_core
    warm_up(run_data_query_core, model_key=model_key)
