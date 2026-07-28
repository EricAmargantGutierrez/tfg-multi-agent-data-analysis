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
from src.llm import build_llm


def generate_report_core(history: list) -> dict:
    try:
        llm = build_llm()
        prompt = json.dumps(history, indent=2)

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
