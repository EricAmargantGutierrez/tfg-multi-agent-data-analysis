"""
src/core/retry.py

The one self-correcting retry loop, shared by the Data Query, Viz, and
Analysis agents.
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
