"""
src/core/llm_json.py

One shared helper for the "LLM was asked to return JSON" pattern used by
the router, the Viz planner, and the Analysis planner. Previously each
had its own copy-pasted ```json fence stripping.
"""
from __future__ import annotations

import json


def parse_llm_json(text: str) -> dict:
    if text is None:
        raise ValueError("LLM returned empty content.")

    cleaned = text.strip().replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM did not return valid JSON: {exc}. Raw: {cleaned[:300]!r}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"LLM JSON response must be an object, got {type(data).__name__}.")

    return data
