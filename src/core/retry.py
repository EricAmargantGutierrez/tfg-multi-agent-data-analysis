"""
src/core/retry.py

The one self-correcting retry loop, shared by the SQL, Viz, and Analysis
agents (previously copy-pasted three times, nearly identically).

Usage:
    def step(error_context):
        # ... generate + execute, using error_context to correct a prior
        # failure ...
        return {"columns": [...], "rows": [...], "sql": "..."}   # no ok/attempts/error

    result = run_self_correcting(step, max_retries=3,
                                  failure_defaults={"columns": [], "rows": [], "sql": None})

On success: result has ok=True, attempts=N, retried=(N>1), error=None, plus
whatever keys `step` returned.
On exhausting retries: result is failure_defaults merged with
ok=False, attempts=max_retries, retried=True, error=<last exception message>.
"""
from __future__ import annotations

from typing import Any, Callable


def run_self_correcting(
    step: Callable[[str | None], dict[str, Any]],
    max_retries: int = 3,
    failure_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    error_context: str | None = None
    last_error = ""

    for attempt in range(1, max_retries + 1):
        try:
            result = step(error_context)
            result["ok"] = True
            result["attempts"] = attempt
            result["retried"] = attempt > 1
            result["error"] = None
            return result
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            error_context = last_error

    out = dict(failure_defaults or {})
    out.update(ok=False, attempts=max_retries, retried=True, error=last_error)
    return out
