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

        if result["ok"]:

            if "path" in result:
                print("Chart created.")
                print(result["path"])

            elif "answer" in result:
                print(result["answer"])

            else:
                print(result)

        else:
            print(result["error"])

        print()

    print("\nGenerating report...")

    result = anyio.run(
        call_agent_tool,
        "report",
        {
            "history": history,
        },
    )

    print(f"Report saved to {result['answer']['path']}")


if __name__ == "__main__":
    main()