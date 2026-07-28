from fastmcp import FastMCP

from src.agents.viz.engine import generate_chart_core

mcp = FastMCP("VisualizationAgent")


@mcp.tool()
def generate_chart(question: str) -> dict:
    """Natural language question -> chart."""
    return generate_chart_core(question)


if __name__ == "__main__":
    mcp.run()
