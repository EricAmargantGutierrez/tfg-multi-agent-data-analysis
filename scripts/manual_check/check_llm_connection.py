"""
Manual smoke check -- NOT part of the automated test suite (tests/), since
it makes a real API call and needs a live key. Must be run by hand when you want
to confirm your .env / provider config is working:

    PYTHONPATH=. python scripts/manual_check/check_llm_connection.py
"""
from src.llm import build_llm


def main():
    llm = build_llm()
    response = llm.invoke("Say only: connection successful.")
    print(response.content)


if __name__ == "__main__":
    main()
