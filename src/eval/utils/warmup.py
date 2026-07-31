"""
src/eval/utils/warmup.py

One throwaway call, through the EXACT SAME code path as the real timed
calls about to follow, before timing anything for real.

Matters most for local models (Ollama). Learned the hard way, twice:
  1. A trivial "Say OK" call did NOT absorb the cold-start cost of a
     real, longer, structured call -- the first real question still
     took 177s vs 7-15s for the rest.
  2. A single warm-up using run_sql_core() only covered the SQL Agent's
     code path -- when correctness_benchmark.py moved on to the
     Baseline and Monolithic sides (different functions), EACH one's
     first call paid its own separate ~90s setup cost, because nothing
     had warmed up THAT specific call shape yet.

Conclusion: there isn't one universal "the model is warm now" state to
reach with a single call. Each genuinely different call shape (different
function, different code path) needs its OWN warm-up, immediately before
its own timed loop starts.
"""
import time


def warm_up(call_fn, question: str = "How many orders are there?", model_key: str | None = None) -> None:
    """call_fn: any callable taking a question string (optionally a
    model_key kwarg) -- e.g. run_sql_core, run_single_agent,
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
    """Back-compat convenience: warms up via the SQL Agent specifically.
    Prefer warm_up(your_actual_function) when the real timed loop uses a
    different function -- see the module docstring for why this matters."""
    from src.agents.sql.engine import run_sql_core
    warm_up(run_sql_core, model_key=model_key)
