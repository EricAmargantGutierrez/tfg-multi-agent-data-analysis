from pathlib import Path

from src.agents.base import BaseAgent


class ReportAgent(BaseAgent):

    def __init__(self):
        super().__init__("report")

    def run(self, history):

        report = "# Session Report\n\n"

        for i, turn in enumerate(history, start=1):

            report += f"## Question {i}\n"
            report += f"{turn['question']}\n\n"

            report += "### Answer\n"

            answer = turn["answer"]

            if isinstance(answer, dict):
                report += str(answer)
            else:
                report += answer

            report += "\n\n"

        output = Path("results/session_report.md")
        output.write_text(report, encoding="utf-8")

        return self.success(
            {
                "path": str(output)
            }
        )