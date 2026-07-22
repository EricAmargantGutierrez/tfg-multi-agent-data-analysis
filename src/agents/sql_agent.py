from __future__ import annotations

from src.agents.base import BaseAgent
from src.database.manager import DatabaseManager


class SQLAgent(BaseAgent):

    def __init__(self):
        super().__init__("sql")
        self.db = DatabaseManager()

    def run(self, question: str):

        q = question.lower()

        if "count" in q or "how many" in q or "orders" in q:
            sql = """
            SELECT COUNT(*) AS total_orders
            FROM orders
            """

        elif "total sales" in q or "sales" in q:
            sql = """
            SELECT SUM(sales) AS total_sales
            FROM orders
            """

        elif "profit" in q and "average" in q:
            sql = """
            SELECT AVG(profit) AS average_profit
            FROM orders
            """

        elif "sales by region" in q or "region" in q:
            sql = """
            SELECT region,
                   SUM(sales) AS total_sales
            FROM orders
            GROUP BY region
            ORDER BY total_sales DESC
            """

        else:
            return self.error(
                "I don't know how to answer that yet."
            )

        result = self.db.execute(sql)

        return self.success(result)