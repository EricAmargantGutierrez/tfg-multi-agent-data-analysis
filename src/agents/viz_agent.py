from src.agents.base import BaseAgent
from src.database.chart_engine import generate_chart_core


class VisualizationAgent(BaseAgent):

    def __init__(self):

        super().__init__("viz")

    def run(self, question):

        try:

            result = generate_chart_core(question)

            return self.success(result)

        except Exception as e:

            return self.error(str(e))