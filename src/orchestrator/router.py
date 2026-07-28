"""
src/orchestrator/router.py

Two-tier routing: an LLM decides which agent should handle a question,
with a keyword-based fallback for when the LLM is unavailable or returns
garbage (common with weaker local models).
"""
from __future__ import annotations

import json

from src.core.llm_json import parse_llm_json
from src.llm import build_llm
from src.models.schemas import RoutingDecision

AGENTS = {
    "sql": "Retrieve or aggregate data from the database.",
    "analysis": "Perform statistical or machine learning analyses over the dataset.",
    "viz": "Generate charts or visualizations.",
    "report": "Generate a report summarizing the session.",
}

SYSTEM_PROMPT = f"""
You are a routing assistant.

Available agents:

{json.dumps(AGENTS, indent=2)}

Reply ONLY with valid JSON. Example: {{"agent":"sql"}}
"""

_VIZ_WORDS = ("plot", "chart", "graph", "visual")
_ANALYSIS_WORDS = (
    "mean", "average", "median", "mode", "variance", "standard deviation",
    "std", "correlation", "covariance", "regression", "pca",
    "principal component", "cluster", "kmeans", "t-test", "ttest", "statistics",
)


def keyword_route(question: str) -> str:
    """
    Order matters: an explicit request to generate the report should win
    even if the question also contains a statistical term (e.g. "generate
    a report showing the average profit"). Report intent is checked first.
    """
    q = question.lower()

    if "report" in q:
        return "report"

    if any(word in q for word in _VIZ_WORDS):
        return "viz"

    if any(word in q for word in _ANALYSIS_WORDS):
        return "analysis"

    return "sql"


def route(question: str) -> str:
    llm = build_llm()
    try:
        response = llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ])
        data = parse_llm_json(response.content)
        decision = RoutingDecision(**data)
        return decision.agent
    except Exception:
        # Covers LLM/network errors, bad JSON, and RoutingDecision
        # validation failures alike -- any of these fall back to keywords.
        pass

    return keyword_route(question)
