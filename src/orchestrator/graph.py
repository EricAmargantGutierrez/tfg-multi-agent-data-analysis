"""
LangGraph orchestrator.
"""

from __future__ import annotations

import anyio

from langgraph.graph import END, StateGraph

from src.orchestrator.mcp_clients import call_agent_tool
from src.orchestrator.narrate import narrate
from src.orchestrator.router import route
from src.orchestrator.state import SessionState


# ------------------------------------------------------------------
# Nodes
# ------------------------------------------------------------------

def router_node(state: SessionState):

    state["route"] = route(state["question"])
    return state


def agent_node(state: SessionState):

    selected = state["route"]

    if selected == "sql":

        state["result"] = anyio.run(
            call_agent_tool,
            "sql",
            {
                "question": state["question"],
            },
        )

    elif selected == "analysis":

        state["result"] = anyio.run(
            call_agent_tool,
            "analysis",
            {
                "question": state["question"],
            },
        )

    elif selected == "viz":

        state["result"] = anyio.run(
            call_agent_tool,
            "viz",
            {
                "question": state["question"],
            },
        )

    elif selected == "report":

        state["result"] = anyio.run(
            call_agent_tool,
            "report",
            {
                "history": state["history"],
            },
        )

    else:

        state["result"] = {
            "ok": False,
            "error": f"Unknown route: {selected}",
        }

    return state


# ------------------------------------------------------------------
# Graph
# ------------------------------------------------------------------

graph_builder = StateGraph(SessionState)

graph_builder.add_node("router", router_node)
graph_builder.add_node("agent", agent_node)

graph_builder.set_entry_point("router")

graph_builder.add_edge("router", "agent")
graph_builder.add_edge("agent", END)

graph = graph_builder.compile()


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def answer(question: str, history: list | None = None):

    if history is None:
        history = []

    state = {
        "question": question,
        "history": history,
    }

    result = graph.invoke(state)

    agent = result["route"]
    raw_result = result["result"]

    history.append(
        {
            "question": question,
            "agent": agent,
            "result": raw_result,
        }
    )

    narrated = narrate(
        question=question,
        agent=agent,
        result=raw_result,
    )

    return {
        "ok": raw_result["ok"],
        "answer": narrated,
        "raw": raw_result,
    }