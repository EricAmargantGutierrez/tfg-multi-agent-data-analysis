from src.agents.sql_agent import SQLAgent


def main():

    agent = SQLAgent()

    result = agent.run(
        "How many orders are there?"
    )

    print(result)


if __name__ == "__main__":
    main()