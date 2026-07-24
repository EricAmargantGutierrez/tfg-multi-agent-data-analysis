from __future__ import annotations

import json

from src.agents.base import BaseAgent
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


class AnalysisAgent(BaseAgent):

    def __init__(self):

        super().__init__("analysis")

    def run(self, data):

        if not data:

            return self.error("No data received.")

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

            return self.success(response.content)

        except Exception as e:

            return self.error(str(e))