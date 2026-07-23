import json

from src.llm import build_llm

AGENTS = {
    "sql": "Retrieve or aggregate data from the database.",
    "viz": "Generate charts or visualizations.",
    "analysis": "Perform statistical analysis.",
    "report": "Generate a report summarizing the session."
}

SYSTEM_PROMPT = f"""
You are a routing assistant.

Your task is to choose which agent should answer the user's question.

Available agents:

{json.dumps(AGENTS, indent=2)}

Reply ONLY with valid JSON.

Example:

{{"agent":"sql"}}
"""


def keyword_route(question: str) -> str:
    """
    Fallback router if the LLM fails.
    """

    q = question.lower()

    if any(word in q for word in ["plot", "chart", "graph", "visual"]):
        return "viz"

    if any(word in q for word in ["average", "correlation", "variance", "distribution"]):
        return "analysis"

    if "report" in q:
        return "report"

    return "sql"


def route(question: str) -> str:

    llm = build_llm()

    try:

        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ])

        raw = response.content.strip()

        data = json.loads(raw)

        if data["agent"] in AGENTS:
            return data["agent"]

    except Exception:

        pass

    return keyword_route(question)