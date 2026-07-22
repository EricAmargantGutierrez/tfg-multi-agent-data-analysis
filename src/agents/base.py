"""
Base class for all agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseAgent(ABC):
    """
    Base class for every agent in the system.
    """

    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, question: str) -> dict[str, Any]:
        """
        Execute the agent.
        """
        pass

    def success(self, answer: Any) -> dict[str, Any]:
        """
        Standard successful response.
        """
        return {
            "ok": True,
            "agent": self.name,
            "answer": answer,
        }

    def error(self, message: str) -> dict[str, Any]:
        """
        Standard error response.
        """
        return {
            "ok": False,
            "agent": self.name,
            "error": message,
        }