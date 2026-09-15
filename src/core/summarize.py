"""
src/core/summarize.py

Agent results can hold large row lists (e.g. a Viz Agent scatter result
capped at MAX_ROWS=1000, or an unaggregated Data Query answer). Putting
these raw into an LLM prompt isn't useful and can push a request past
the provider's token limit -- this actually caused a 413 error during
narration and a ~14,700-token report-generation request before this fix.

One shared recursive summarizer, used by both narration and report
generation instead of each having its own fix.
"""
from __future__ import annotations

from typing import Any

MAX_ROWS_IN_PROMPT = 15
SAMPLE_ROWS_SHOWN = 5


def summarize_large_rows(obj: Any) -> Any:
    """Walk a dict/list structure. Any list longer than MAX_ROWS_IN_PROMPT
    whose elements are dicts or lists (row-shaped data, not a short list
    of floats like PCA's explained_variance_ratio) gets replaced with a
    compact summary. Everything else passes through unchanged."""
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
