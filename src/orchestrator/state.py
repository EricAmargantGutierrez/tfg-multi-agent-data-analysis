from typing import TypedDict


class SessionState(TypedDict):

    question: str

    route: str

    result: dict

    history: list