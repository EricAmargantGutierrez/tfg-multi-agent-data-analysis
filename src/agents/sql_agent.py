from fastmcp import FastMCP

from src.database.sql_engine import run_sql_core


mcp = FastMCP("SQLAgent")


@mcp.tool()
def run_sql(question: str) -> dict:
    """
    Natural language question -> SQL.
    """
    return run_sql_core(question)


if __name__ == "__main__":
    mcp.run()