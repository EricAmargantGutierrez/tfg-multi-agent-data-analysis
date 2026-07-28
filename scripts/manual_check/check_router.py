"""
Manual smoke check -- NOT part of the automated test suite. Prints how the
LIVE LLM router classifies a handful of example questions. For the offline,
CI-safe routing tests (including the keyword-fallback edge cases), see
tests/test_router.py instead.

    PYTHONPATH=. python scripts/manual_check/check_router.py
"""
from src.orchestrator.router import route

QUESTIONS = [
    "How many orders are there?",
    "Create a bar chart of sales by region.",
    "Calculate the average profit.",
    "Generate the final report.",
]

for q in QUESTIONS:
    print(q)
    print(" ->", route(q))
    print()
