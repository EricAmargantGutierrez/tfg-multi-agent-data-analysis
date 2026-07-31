"""
src/agents/report/engine.py

Report Agent core logic, extracted out of agent.py so it's directly unit
testable (previously this agent was the only one of the four without an
engine module, so it could only be exercised through FastMCP).
"""
from __future__ import annotations

import json

from src.agents.report.prompts import SYSTEM_PROMPT
from src.core.paths import RESULTS_DIR
from src.core.summarize import summarize_large_rows
from src.llm import build_llm


def generate_report_core(history: list) -> dict:
    try:
        llm = build_llm()
        # Each turn's raw result can contain a large row list (e.g. a
        # boxplot/scatter/histogram result, or an unaggregated SQL
        # query) -- summarized before serializing, or a session with a
        # few large-row charts can blow a single request past the
        # provider's token limit. See src/core/summarize.py.
        prompt = json.dumps(summarize_large_rows(history), indent=2)

        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ])

        RESULTS_DIR.mkdir(exist_ok=True)
        output = RESULTS_DIR / "session_report.md"
        output.write_text(response.content, encoding="utf-8")

        return {"ok": True, "answer": {"path": str(output)}}

    except Exception as e:
        return {"ok": False, "error": str(e)}
