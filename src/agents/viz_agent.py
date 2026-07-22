from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt

from src.agents.base import BaseAgent
from src.database.manager import DatabaseManager
from src.core.paths import RESULTS_DIR


class VisualizationAgent(BaseAgent):

    def __init__(self):
        super().__init__("viz")
        self.db = DatabaseManager()

    def run(self, question: str):

        rows = self.db.execute("""
            SELECT region,
                   SUM(sales) AS total_sales
            FROM orders
            GROUP BY region
            ORDER BY total_sales DESC
        """)

        regions = [r["region"] for r in rows]
        sales = [r["total_sales"] for r in rows]

        plt.figure(figsize=(8,5))
        plt.bar(regions, sales)
        plt.title("Sales by Region")
        plt.xlabel("Region")
        plt.ylabel("Sales")
        plt.tight_layout()

        RESULTS_DIR.mkdir(exist_ok=True)

        output = RESULTS_DIR / "sales_by_region.png"

        plt.savefig(output)
        plt.close()

        return self.success({
            "path": str(output),
            "rows": rows
        })