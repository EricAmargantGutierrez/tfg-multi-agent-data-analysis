from __future__ import annotations

import json
from pathlib import Path

from src.agents.base import BaseAgent
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


class ReportAgent(BaseAgent):

    def __init__(self):

        super().__init__("report")

    def run(self, history):

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

            return self.success(
                {
                    "path": str(output)
                }
            )

        except Exception as e:

            return self.error(str(e))