"""
Simple router.

Decides which agent should handle the user's request.
"""

from __future__ import annotations


def route(question: str) -> str:
    """
    Route a question to the appropriate agent.
    """

    q = question.lower()

    sql_keywords = [
        "sales",
        "profit",
        "customer",
        "order",
        "quantity",
        "discount",
        "state",
        "city",
        "region",
        "category",
        "product",
        "table",
        "average",
        "sum",
        "count",
        "maximum",
        "minimum",
        "total",
    ]

    viz_keywords = [
        "plot",
        "chart",
        "graph",
        "histogram",
        "bar",
        "line",
        "scatter",
        "visualize",
    ]

    report_keywords = [
        "report",
        "summary",
    ]

    if any(word in q for word in viz_keywords):
        return "viz"

    if any(word in q for word in report_keywords):
        return "report"

    if any(word in q for word in sql_keywords):
        return "sql"

    return "analysis"