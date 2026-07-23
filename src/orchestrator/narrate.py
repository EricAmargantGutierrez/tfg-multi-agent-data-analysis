"""
narrate.py — The LLM's SECOND job: turn raw agent output into human prose.

A proposal's signature example: [("West", 184231.5), ...] becomes
"The West region led in total sales with $184,231...". This module does exactly
that, per agent type.
"""
from __future__ import annotations

from typing import Any

from src.llm import build_llm

NARRATE_SYSTEM = (
    "You turn a data agent's raw output into a clear, concise answer for a "
    "business user. State concrete numbers. 1-3 sentences unless a table is "
    "clearer. Do not invent data not present in the raw output."
)


def narrate(question: str, agent: str, result: dict[str, Any],
            *, model_key: str | None = None) -> str:
    if not result.get("ok"):
        return (f"I couldn't answer that (agent: {agent}). "
                f"Error after {result.get('attempts','?')} attempts: "
                f"{result.get('error')}")
    llm = build_llm(model_key)
    if agent == "sql":
        payload = {"columns": result["columns"], "rows": result["rows"][:50]}
    elif agent == "analysis":
        payload = {"result": result["result"]}
    elif agent == "viz":
        payload = {"chart_saved_to": result["path"],
                   "plotted_data": result["data"]}
    elif agent == "report":
        return f"Report generated: {result['path']}"
    else:
        payload = result
    user = (f"Question: {question}\nAgent: {agent}\nRaw output: {payload}\n"
            "Write the answer.")
    resp = llm.invoke([{"role": "system", "content": NARRATE_SYSTEM},
                       {"role": "user", "content": user}])
    return resp.content if isinstance(resp.content, str) else str(resp.content)