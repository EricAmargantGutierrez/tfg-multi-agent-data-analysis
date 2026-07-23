from src.orchestrator.router import route


questions = [
    "How many orders are there?",
    "Create a bar chart of sales by region.",
    "Calculate the average profit.",
    "Generate the final report."
]

for q in questions:

    print(q)

    print(route(q))

    print()