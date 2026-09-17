from __future__ import annotations

from fastmcp import FastMCP

from src.agents.report.engine import generate_report_core

mcp = FastMCP("ReportAgent")


@mcp.tool()
def generate_report(history: list, language: str | None = None) -> dict:
    """Generate the final Markdown report."""
    return generate_report_core(history, language)


if __name__ == "__main__":
    mcp.run()
