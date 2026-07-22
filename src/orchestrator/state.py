"""
Defines the session state.
"""

from typing import TypedDict


class SessionState(TypedDict):
    question: str
    route: str
    answer: str