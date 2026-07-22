"""
Simple orchestrator (Version 1).
"""

from __future__ import annotations

from src.agents.sql_agent import SQLAgent
from src.orchestrator.router import route


class Graph:

    def __init__(self):

        self.sql_agent = SQLAgent()

    def answer(self, question: str):

        selected_agent = route(question)

        if selected_agent == "sql":
            return self.sql_agent.run(question)

        return {
            "ok": False,
            "agent": selected_agent,
            "error": f"{selected_agent} agent not implemented yet."
        }