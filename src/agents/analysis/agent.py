from __future__ import annotations

from fastmcp import FastMCP

from src.agents.analysis.engine import run_analysis_core

mcp = FastMCP("AnalysisAgent")


@mcp.tool
def run_analysis(question: str, model_key: str | None = None, max_retries: int = 3) -> dict:
    """Execute a statistical analysis over the dataset."""
    return run_analysis_core(question=question, model_key=model_key, max_retries=max_retries)


if __name__ == "__main__":
    mcp.run()
