"""
src/core/summarize.py

Agent results can contain large row lists -- e.g. the Viz Agent's
scatter/histogram/boxplot results, capped at src.core.db.MAX_ROWS = 1000,
or a SQL Agent question with no aggregation ("list all products" ->
~1850 rows). Dumping these raw into an LLM prompt is neither useful (an
LLM reading 1000 raw (x, y) pairs cannot summarize a chart any better
than one reading a count + a few samples) nor safe -- it can push a
single request past a provider's per-request/per-minute token limit.

Observed in practice, twice, in two different places before this fix:
  1. Narration (src.orchestrator.narrate): a 1000-row scatter result
     narrated directly triggered a 413 "Request too large" error.
  2. Report generation (src.agents.report.engine): a session with
     several large-row chart results serialized via json.dumps(history)
     produced a single ~14,700-token request.

Both now share this one recursive summarizer instead of each having (or
one having, and the other lacking) its own ad hoc fix.
"""
from __future__ import annotations

from typing import Any

MAX_ROWS_IN_PROMPT = 15
SAMPLE_ROWS_SHOWN = 5


def summarize_large_rows(obj: Any) -> Any:
    """Recursively walk a dict/list structure. Any list longer than
    MAX_ROWS_IN_PROMPT whose elements are themselves dicts or lists (i.e.
    row-shaped data, not a short list of floats like PCA's
    explained_variance_ratio or regression's coefficients) is replaced
    with a compact summary. Everything else passes through unchanged."""
    if isinstance(obj, dict):
        return {k: summarize_large_rows(v) for k, v in obj.items()}

    if isinstance(obj, list):
        row_shaped = len(obj) > 0 and isinstance(obj[0], (dict, list))
        if len(obj) > MAX_ROWS_IN_PROMPT and row_shaped:
            return {
                "total_rows": len(obj),
                "sample_first_rows": [summarize_large_rows(x) for x in obj[:SAMPLE_ROWS_SHOWN]],
                "note": f"{len(obj)} rows total; showing the first {SAMPLE_ROWS_SHOWN} as a sample.",
            }
        return [summarize_large_rows(x) for x in obj]

    return obj
