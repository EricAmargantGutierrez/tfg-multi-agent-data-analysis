from __future__ import annotations

import os
import sys

from fastmcp import Client

from src.agents.sql.agent import mcp as sql_mcp
from src.agents.viz.agent import mcp as viz_mcp
from src.agents.analysis.agent import mcp as analysis_mcp
from src.agents.report.agent import mcp as report_mcp


AGENT_REGISTRY = {
    "sql": (sql_mcp, "src.agents.sql.agent", "run_sql"),
    "viz": (viz_mcp, "src.agents.viz.agent", "generate_chart"),
    "analysis": (analysis_mcp, "src.agents.analysis.agent", "run_analysis"),
    "report": (report_mcp, "src.agents.report.agent", "generate_report"),
}


async def call_agent_tool(agent_name: str, tool_args: dict) -> dict:
    transport = os.getenv("TFG_MCP_TRANSPORT", "memory")

    if agent_name not in AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}")

    server_obj, module_path, tool_name = AGENT_REGISTRY[agent_name]

    if transport == "memory":
        async with Client(server_obj) as client:
            result = await client.call_tool(tool_name, tool_args)
    else:
        # sys.executable, not a bare "python" string: guarantees the
        # subprocess uses the same interpreter/venv as the orchestrator,
        # instead of whatever "python" happens to resolve to on $PATH.
        async with Client(command=sys.executable, args=["-m", module_path]) as client:
            result = await client.call_tool(tool_name, tool_args)

    return result.data if hasattr(result, "data") else result
