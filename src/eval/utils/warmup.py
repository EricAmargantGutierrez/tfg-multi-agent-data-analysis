"""
src/eval/utils/warmup.py

Makes one throwaway call through the exact same code path as the real
timed calls, before any real timing starts.

Matters most for local models (Ollama). Found out the hard way, twice:
  1. A simple "Say OK" call did NOT cover the cold-start cost of a real,
     longer, structured call - the first real question still took 177s
     while the rest took 7-15s.
  2. Warming up once with run_data_query_core() only covered the Data
     Query Agent's code path - when correctness_benchmark.py moved on to
     the Baseline and Monolithic sides (different functions), each one's
     first call still paid its own ~90s setup cost, because nothing had
     warmed up that specific kind of call yet.

So there's no single "the model is warm now" you can reach with one
call. Each genuinely different kind of call (different function,
different code path) needs its own warm-up, right before its own timed
loop starts.
"""
import time


def warm_up(call_fn, question: str = "How many orders are there?", model_key: str | None = None) -> None:
    """call_fn: any callable taking a question string (optionally a
    model_key kwarg) -- e.g. run_data_query_core, run_single_agent,
    run_monolithic_agent, or src.orchestrator.graph.answer wrapped to
    match this signature. Failures are swallowed: a warm-up call exists
    to pay a cost, not to be scored -- if it errors, the real loop will
    surface the same error for real, scored, questions anyway."""
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
    """Back-compat convenience: warms up via the Data Query Agent specifically.
    Prefer warm_up(your_actual_function) when the real timed loop uses a
    different function -- see the module docstring for why this matters."""
    from src.agents.data_query.engine import run_data_query_core
    warm_up(run_data_query_core, model_key=model_key)
