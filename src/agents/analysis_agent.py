from __future__ import annotations

from src.agents.base import BaseAgent


class AnalysisAgent(BaseAgent):

    def __init__(self):
        super().__init__("analysis")

    def run(self, data):

        if not data:
            return self.error("No data received.")

        if isinstance(data, list):

            if len(data) == 1:

                row = data[0]

                text = "Result:\n"

                for key, value in row.items():
                    text += f"- {key}: {value}\n"

                return self.success(text)

            text = f"The query returned {len(data)} rows."

            return self.success(text)

        return self.error("Unsupported input.")