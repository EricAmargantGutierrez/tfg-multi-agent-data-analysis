"""
src/agents/report/engine.py

Report Agent core logic, kept out of agent.py so it's unit testable
without going through FastMCP.
"""
from __future__ import annotations

import json

from src.agents.report.prompts import build_system_prompt
from src.core.paths import RESULTS_DIR
from src.core.summarize import summarize_large_rows
from src.llm import build_llm


def generate_report_core(history: list, language: str | None = None) -> dict:
    try:
        llm = build_llm()
        # A turn's raw result can hold a large row list (e.g. an
        # unaggregated query) -- summarize first or it can blow past the
        # provider's token limit. See src/core/summarize.py.
        prompt = json.dumps(summarize_large_rows(history), indent=2)

        response = llm.invoke([
            {"role": "system", "content": build_system_prompt(language)},
            {"role": "user", "content": prompt},
        ])

        RESULTS_DIR.mkdir(exist_ok=True)
        output = RESULTS_DIR / "session_report.md"
        output.write_text(response.content, encoding="utf-8")

        return {"ok": True, "answer": {"path": str(output)}}

    except Exception as e:
        return {"ok": False, "error": str(e)}
