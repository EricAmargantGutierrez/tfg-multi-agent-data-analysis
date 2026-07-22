from src.orchestrator.router import route


def main():

    questions = [
        "How many orders are there?",
        "Show total sales by region",
        "Create a bar chart",
        "Generate a report",
        "Why are profits decreasing?",
    ]

    for q in questions:
        print(q)
        print(" ->", route(q))
        print()


if __name__ == "__main__":
    main()