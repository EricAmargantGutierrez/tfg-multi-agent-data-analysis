from src.llm import build_llm


def main():

    llm = build_llm()

    print(type(llm))


if __name__ == "__main__":
    main()