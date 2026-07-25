from __future__ import annotations

import json

from fastmcp import FastMCP

from src.core.paths import RESULTS_DIR
from src.llm import build_llm


SYSTEM_PROMPT = """
You are a senior data analyst.

Write a professional report based on a conversation between a user and a
multi-agent data analysis system.

The report should contain:

# Executive Summary

# Questions Asked

# Key Findings

# Conclusions

Use Markdown.
Be concise.
Do not invent information.
"""


mcp = FastMCP("ReportAgent")


@mcp.tool()
def generate_report(history: list) -> dict:
    """
    Generate the final Markdown report.
    """

    try:

        llm = build_llm()

        prompt = json.dumps(history, indent=2)

        response = llm.invoke([
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ])

        RESULTS_DIR.mkdir(exist_ok=True)

        output = RESULTS_DIR / "session_report.md"

        output.write_text(
            response.content,
            encoding="utf-8",
        )

        return {
            "ok": True,
            "answer": {
                "path": str(output)
            }
        }

    except Exception as e:

        return {
            "ok": False,
            "error": str(e)
        }


if __name__ == "__main__":
    mcp.run()