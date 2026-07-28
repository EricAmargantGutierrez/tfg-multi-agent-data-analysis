"""
Convert raw agent outputs into human-readable responses.
"""
from __future__ import annotations

from src.llm import build_llm

SYSTEM_PROMPT = """
You are a data analyst.

Your task is to explain the output produced by a data analysis system.

Rules:

- Answer the user's original question.
- Be concise.
- Mention the important numbers.
- Do not invent information.
- If the result contains multiple rows, summarize them naturally.
- If an error occurred, explain it clearly.
"""


def narrate(question: str, agent: str, result: dict) -> str:
    if not result.get("ok", False):
        return result.get("error", "Unknown error.")

    if agent == "report":
        path = result.get("answer", {}).get("path", "unknown location")
        return f"Report successfully generated.\n\nLocation: {path}"

    llm = build_llm()

    prompt = (
        f"User question:\n\n{question}\n\n"
        f"Agent:\n\n{agent}\n\n"
        f"Raw output:\n\n{result}\n\n"
        "Generate the final response for the user."
    )

    response = llm.invoke([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ])

    return response.content
