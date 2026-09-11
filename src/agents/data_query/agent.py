"""
src/agents/data_query/agent.py - MCP server exposing the Data Query Agent.

Thin wrapper only. All logic lives in engine.py so it can be unit tested
without spinning up FastMCP.
"""
from fastmcp import FastMCP

from src.agents.data_query.engine import run_data_query_core

mcp = FastMCP("DataQueryAgent")


@mcp.tool()
def run_data_query(question: str) -> dict:
    """Natural language question -> SQL -> structured rows."""
    return run_data_query_core(question)


if __name__ == "__main__":
    mcp.run()
