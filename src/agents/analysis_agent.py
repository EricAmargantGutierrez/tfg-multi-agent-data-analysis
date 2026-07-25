from __future__ import annotations

import json

from fastmcp import FastMCP

from src.llm import build_llm


SYSTEM_PROMPT = """
You are a professional data analyst.

Your task is to explain SQL query results to a business user.

Rules:

- Be concise.
- Mention the important numbers.
- Do not invent information.
- If appropriate, explain what the result means.
"""


mcp = FastMCP("AnalysisAgent")


@mcp.tool()
def run_analysis(data: dict) -> dict:
    """
    Explain SQL query results.
    """

    if not data:
        return {
            "ok": False,
            "error": "No data received."
        }

    try:

        llm = build_llm()

        prompt = f"""
The following data comes from a SQL query.

{json.dumps(data, indent=2)}

Explain the results in natural language.
"""

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

        return {
            "ok": True,
            "answer": response.content,
        }

    except Exception as e:

        return {
            "ok": False,
            "error": str(e),
        }


if __name__ == "__main__":
    mcp.run()