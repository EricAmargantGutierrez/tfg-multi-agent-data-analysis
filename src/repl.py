"""
Interactive REPL.
"""

import anyio

from src.orchestrator.graph import answer
from src.orchestrator.mcp_clients import call_agent_tool


def main():

    history = []

    print("\nMulti-Agent Data Analysis System")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("You > ").strip()

        if question.lower() in {"exit", "quit", "done"}:
            break

        result = answer(question, history)

        print("\nAssistant >")

        print(result["answer"])

        raw = result.get("raw", {})

        if raw.get("path"):

            print(f"\nGenerated file: {raw['path']}")

        print()

    print("\nGenerating report...")

    report = anyio.run(
        call_agent_tool,
        "report",
        {
            "history": history,
        },
    )

    if report["ok"]:

        print(f"Report saved to {report['answer']['path']}")

    else:

        print(f"Error generating report: {report['error']}")


if __name__ == "__main__":
    main()