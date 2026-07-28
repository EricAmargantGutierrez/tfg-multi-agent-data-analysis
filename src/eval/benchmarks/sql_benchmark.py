from src.agents.sql_agent import run_sql_core
from src.eval.benchmark_runner import run_benchmark

run_benchmark(
    agent_name="SQL Agent",
    output_file="results/sql_agent_results.json",
    answer_function=run_sql_core,
)