"""
Interactive REPL.
"""

from src.orchestrator.graph import answer
from src.agents.report_agent import ReportAgent


def main():

    history = []
    report_agent = ReportAgent()

    print("\nMulti-Agent Data Analysis System")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("You > ").strip()

        if question.lower() in {"exit", "quit", "done"}:
            break

        result = answer(question, history)

        print("\nAssistant >")

        if result["ok"]:

            if isinstance(result["answer"], dict):

                if "path" in result["answer"]:
                    print("Chart created.")
                    print(result["answer"]["path"])
                else:
                    print(result["answer"])

            else:
                print(result["answer"])

        else:
            print(result["error"])

        print()

    print("\nGenerating report...")

    result = report_agent.run(history)

    print(f"Report saved to {result['answer']['path']}")


if __name__ == "__main__":
    main()