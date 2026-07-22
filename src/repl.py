"""
Interactive REPL.
"""

from src.orchestrator.graph import Graph


def main():

    graph = Graph()

    print("\nMulti-Agent Data Analysis System")
    print("Type 'exit' to quit.\n")

    while True:

        question = input("You > ").strip()

        if question.lower() in {"exit", "quit", "done"}:
            break

        result = graph.answer(question)

        print("\nAssistant >")

        if result["ok"]:
            print(result["answer"])
        else:
            print(result["error"])

        print()


if __name__ == "__main__":
    main()