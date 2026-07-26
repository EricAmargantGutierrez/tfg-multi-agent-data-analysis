from __future__ import annotations

import os

from fastmcp import Client

from src.agents.sql_agent import mcp as sql_mcp
from src.agents.viz_agent import mcp as viz_mcp
from src.agents.analysis_agent import mcp as analysis_mcp
from src.agents.analysis_agent import mcp as analysis_mcp
from src.agents.report_agent import mcp as report_mcp


AGENT_REGISTRY = {
    "sql": (sql_mcp, "src.agents.sql_agent", "run_sql"),
    "viz": (viz_mcp, "src.agents.viz_agent", "generate_chart"),
    "analysis": (
        analysis_mcp,
        "src.agents.analysis_agent",
        "run_analysis",
    ),
    "report": (report_mcp, "src.agents.report_agent", "generate_report"),
}


async def call_agent_tool(agent_name: str, tool_args: dict) -> dict:

    transport = os.getenv("TFG_MCP_TRANSPORT", "memory")

    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}")

    server_obj, module_path, tool_name = AGENT_REGISTRY[agent_name]

    if transport == "memory":

        async with Client(server_obj) as client:

            result = await client.call_tool(
                tool_name,
                tool_args,
            )

    else:

        async with Client(
            command="python",
            args=["-m", module_path],
        ) as client:

            result = await client.call_tool(
                tool_name,
                tool_args,
            )

    return result.data if hasattr(result, "data") else result