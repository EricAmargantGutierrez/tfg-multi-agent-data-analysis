from src.llm import build_llm


def main():

    llm = build_llm()

    response = llm.invoke(
        "Say only: Groq connection successful."
    )

    print(response.content)


if __name__ == "__main__":
    main()