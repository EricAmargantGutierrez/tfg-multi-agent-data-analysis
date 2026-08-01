# Multi-Agent Conversational Data Analysis System

Bachelor's Thesis (TFG)

**Author:** Eric Amargant Gutiérrez
**Degree:** Bachelor's Degree in Mathematical Engineering in Data Science
**University:** Universitat Pompeu Fabra (UPF)
**Supervisor:** Piotr Przybyła

---

## Overview

This project implements a conversational system that answers natural
language questions over structured datasets using a modular multi-agent
architecture. The system combines Large Language Models (LLMs), LangGraph
for orchestration, and the Model Context Protocol (MCP) to coordinate
specialized agents responsible for SQL querying, statistical analysis,
visualization, and report generation.

The objective is to investigate how agent-based architectures can improve
natural language interaction with structured data, and to empirically
evaluate how much that architecture actually buys you — over a single,
minimally-prompted LLM, and over a single agent with the same tools but
no architectural split — across multiple different underlying models.

---

## Architecture

<p align="center">
  <img src="docs/architecture-diagram.svg" width="900">
</p>

The system consists of four specialized MCP agents coordinated by a
LangGraph orchestrator: **SQL Agent**, **Analysis Agent** (statistics and
ML, including column filters and group-based hypothesis testing),
**Visualization Agent**, and **Report Agent**. All database access is
centralized through `src/core/db.py`, opened strictly read-only. Large
result sets are summarized (`src/core/summarize.py`) before being sent to
an LLM for narration or report generation.

Full details: [`docs/architecture.md`](docs/architecture.md). Evaluation
methodology, results, and failure analysis:
[`results_and_failure_analysis.md`](results_and_failure_analysis.md).
Full development log: [`docs/development_log.md`](docs/development_log.md).

---

## Repository Structure

```text
src/
├── agents/{sql,viz,analysis,report}/   agent.py + engine.py + prompts.py
├── core/                                db.py, retry.py, llm_json.py, summarize.py, paths.py
├── config/settings.py
├── llm/                                 provider-agnostic LLM factory + registry
├── models/schemas.py                    Pydantic validation
├── orchestrator/                        router, MCP client, narrator, LangGraph graph
├── eval/
│   ├── datasets/                        55 questions (sql, analysis, visualization)
│   ├── ground_truth/                    generators, executed against the real DB
│   ├── checks.py                        scoring logic
│   ├── baselines/                       single_agent.py + monolithic_agent.py
│   ├── benchmarks/                      correctness_benchmark.py, pipeline_benchmark.py, report_agent_benchmark.py
│   └── utils/                           evaluator.py, metrics.py, warmup.py
├── ingest.py
└── repl.py

tests/          pytest suite, offline, no API keys needed (116 tests)
docs/           architecture.md, architecture-diagram.svg, development_log.md
results/eval/   tracked; charts (gitignored)
```

---

## Installation

```bash
git clone https://github.com/EricAmargantGutierrez/tfg-multi-agent-data-analysis.git
cd tfg-multi-agent-data-analysis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add your provider key(s). Note: a
`claude.ai` subscription does **not** include API access — that's billed
separately via console.anthropic.com.

Place the Superstore CSV at `data/superstore.csv`
([Kaggle: vivek468/superstore-dataset-final](https://kaggle.com/datasets/vivek468/superstore-dataset-final)),
then:

```bash
python -m src.ingest
```

---

## Running the System

```bash
python -m src.repl
```

---

## Evaluation

```bash
python -m src.eval.ground_truth.generate_sql_ground_truth
python -m src.eval.ground_truth.generate_analysis_ground_truth
python -m src.eval.ground_truth.generate_visualization_ground_truth

python -m src.eval.run_all
python -m src.eval.benchmarks.report_agent_benchmark
```

All benchmark scripts support resuming an interrupted run
(`--side`/`--categories`/`--sessions`).

### Results (55-question benchmark; primary run: Anthropic Claude Haiku 4.5)

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 40.0% | 80.0% | +60.0pp | +20.0pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Routing accuracy: 90.9%. Full breakdowns and a complete question-by-question
failure analysis — including two real issues found by this evaluation
and fixed (a t-test implementation bug and a limitation in the
evaluation's own scoring logic, both independently verified) — are in
[`results_and_failure_analysis.md`](results_and_failure_analysis.md).

---

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

116 tests, entirely offline.

---

## Current Status

Phase 1 (implementation) and Phase 2 (evaluation) are both complete,
including two real fixes found by the evaluation's own failure analysis
and independently verified rather than left as documented limitations.
Remaining: the thesis write-up itself.

---

## License

Developed as part of a Bachelor's Thesis at Universitat Pompeu Fabra.
