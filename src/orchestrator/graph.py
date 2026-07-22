"""
LangGraph orchestrator.
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agents.analysis_agent import AnalysisAgent
from src.agents.sql_agent import SQLAgent
from src.agents.viz_agent import VisualizationAgent
from src.orchestrator.router import route
from src.orchestrator.state import SessionState


# ------------------------------------------------------------------
# Agents
# ------------------------------------------------------------------

sql_agent = SQLAgent()
viz_agent = VisualizationAgent()
analysis_agent = AnalysisAgent()


# ------------------------------------------------------------------
# Nodes
# ------------------------------------------------------------------

def router_node(state: SessionState):

    state["route"] = route(state["question"])
    return state


def agent_node(state: SessionState):

    selected = state["route"]

    if selected == "sql":

        sql_result = sql_agent.run(state["question"])

        if sql_result["ok"]:
            state["result"] = analysis_agent.run(sql_result["answer"])
        else:
            state["result"] = sql_result

    elif selected == "viz":

        state["result"] = viz_agent.run(state["question"])

    else:

        state["result"] = {
            "ok": False,
            "error": f"{selected} agent not implemented yet."
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
        "history": history
    }

    result = graph.invoke(state)

    history.append({
        "question": question,
        "answer": result["result"]
    })

    return result["result"]