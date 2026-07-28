from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
DOCS_DIR = PROJECT_ROOT / "docs"
RESULTS_DIR = PROJECT_ROOT / "results"
BENCHMARK_DIR = PROJECT_ROOT / "benchmark"
TESTS_DIR = PROJECT_ROOT / "tests"

ENV_FILE = PROJECT_ROOT / ".env"
README_FILE = PROJECT_ROOT / "README.md"
