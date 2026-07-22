"""
SQL Agent (Version 1).

Currently executes a fixed SQL query.
"""

from __future__ import annotations

from src.agents.base import BaseAgent
from src.database.manager import DatabaseManager


class SQLAgent(BaseAgent):

    def __init__(self):
        super().__init__("sql")
        self.db = DatabaseManager()

    def run(self, question: str):

        result = self.db.execute(
            """
            SELECT COUNT(*) AS total_orders
            FROM orders
            """
        )

        return self.success(result)