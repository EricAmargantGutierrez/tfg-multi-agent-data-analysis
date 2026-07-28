from src.eval.single_agent import run_single_agent
from src.eval.benchmark_runner import run_benchmark

run_benchmark(
    agent_name="Single Agent",
    output_file="results/single_agent_results.json",
    answer_function=run_single_agent,
)