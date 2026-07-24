from src.agents.base import BaseAgent
from src.database.sql_engine import run_sql_core


class SQLAgent(BaseAgent):

    def __init__(self):
        super().__init__("sql")

    def run(self, question: str):

        result = run_sql_core(question)

        if result["ok"]:
            return self.success(result)

        return self.error(result["error"])