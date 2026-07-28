"""
src/agents/sql/agent.py — MCP server exposing the SQL Agent.

Thin wrapper only. All logic lives in engine.py so it can be unit tested
without spinning up FastMCP.
"""
from fastmcp import FastMCP

from src.agents.sql.engine import run_sql_core

mcp = FastMCP("SQLAgent")


@mcp.tool()
def run_sql(question: str) -> dict:
    """Natural language question -> SQL -> structured rows."""
    return run_sql_core(question)


if __name__ == "__main__":
    mcp.run()
