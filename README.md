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
LangGraph orchestrator:

- **SQL Agent** – Generates and executes read-only SQL queries.
- **Analysis Agent** – Performs statistical analyses and machine learning
  over the retrieved data, including filtering by column conditions
  (region, category, date ranges, etc.).
- **Visualization Agent** – Generates charts from natural language
  requests.
- **Report Agent** – Produces a Markdown report summarizing the session.

The orchestrator routes user requests, invokes the appropriate agent over
MCP, maintains the conversation history, and generates the final response
presented to the user. All database access is centralized through
`src/core/db.py`, opened strictly read-only. Large result sets are
summarized (`src/core/summarize.py`) before being sent to an LLM for
narration or report generation, to avoid exceeding provider request
limits.

A detailed description of the architecture is available in
[`docs/architecture.md`](docs/architecture.md). The evaluation
methodology, full results, and failure analysis are in
[`results_and_failure_analysis.md`](results_and_failure_analysis.md).
The rationale for the restructure applied on top of the original design
is documented in [`MIGRATION.md`](MIGRATION.md); the full evaluation-phase
development log is in
[`docs/development_log.md`](docs/development_log.md) (Milestones 12-13).

---

## Features

- Multi-agent architecture based on FastMCP
- LangGraph orchestration
- LLM-based routing with a keyword fallback
- Natural language to SQL generation
- Statistical analysis and machine learning, with column-filter support
- Automatic SQL validation and self-correction (shared retry logic)
- Automatic chart generation
- Natural language response generation
- Session report generation
- Conversation history (accumulated per session, consumed by the Report Agent)
- Support for multiple LLM providers (Groq, Ollama, OpenAI, Anthropic)
- A full empirical evaluation against two baselines — a minimal
  no-context LLM, and a single agent with identical tools but no
  architectural split — cross-validated across three model providers

---

## Technologies

- Python 3.12
- LangGraph
- FastMCP
- LangChain
- SQLite
- pandas, NumPy, SciPy, scikit-learn
- Matplotlib
- Pydantic (structured validation of LLM outputs)
- Groq, Ollama, OpenAI, Anthropic

---

## Repository Structure

```text
src/
├── agents/
│   ├── safety.py          read-only SQL guard
│   ├── sql/                agent.py + engine.py + prompts.py
│   ├── viz/                agent.py + engine.py + prompts.py
│   ├── analysis/           agent.py + engine.py + prompts.py + statistics.py
│   └── report/             agent.py + engine.py + prompts.py
├── core/
│   ├── db.py               the only module that opens SQLite
│   ├── retry.py            shared self-correction loop
│   ├── llm_json.py         shared "parse LLM JSON output" helper
│   ├── summarize.py        shared large-row-list summarizer (for LLM prompts)
│   └── paths.py
├── config/settings.py
├── llm/                     provider-agnostic LLM factory + model registry
├── models/schemas.py        Pydantic validation (AnalysisPlan, ChartSpec, ...)
├── orchestrator/             router, MCP client, narrator, LangGraph graph
├── eval/
│   ├── datasets/              55 questions (sql, analysis, visualization)
│   ├── ground_truth/          generators, executed against the real DB
│   ├── checks.py               scoring logic (structured output, tolerance-based)
│   ├── baselines/               single_agent.py (minimal) + monolithic_agent.py
│   ├── benchmarks/              correctness_benchmark.py, pipeline_benchmark.py,
│   │                            report_agent_benchmark.py
│   ├── utils/                  evaluator.py, metrics.py, warmup.py
│   └── run_all.py
├── ingest.py                  CSV -> SQLite
└── repl.py                    interactive CLI

scripts/manual_check/        manual live-API smoke scripts (not part of pytest)
tests/                       pytest suite, offline, no API keys needed (103 tests)
docs/                        architecture.md, architecture-diagram.svg, development_log.md
data/                        superstore.csv, superstore.db (gitignored)
results/                     generated charts (gitignored) + results/eval/ (tracked)
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/EricAmargantGutierrez/tfg-multi-agent-data-analysis.git
cd tfg-multi-agent-data-analysis
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and add the key(s) for the model provider(s)
you'll use. Note: `claude.ai` / `console.anthropic.com` subscriptions
(e.g. Claude Pro) do **not** include API access — API usage is billed
separately, pay-as-you-go, via the Anthropic Console.

Place the Superstore CSV at `data/superstore.csv`
([Kaggle: vivek468/superstore-dataset-final](https://kaggle.com/datasets/vivek468/superstore-dataset-final)),
then build the database:

```bash
python -m src.ingest
```

---

## Running the System

Launch the interactive assistant:

```bash
python -m src.repl
```

Example questions:

- How many orders are there?
- Which region has the highest sales?
- What is the average profit in the West region?
- What is the correlation between discount and profit?
- Run a linear regression predicting profit from sales, discount, and quantity.
- Show a line chart of monthly sales.

---

## Evaluation

The full evaluation lives in `src/eval/`; results in `results/eval/`.

```bash
# 1. Generate ground truth against your own database
python -m src.eval.ground_truth.generate_sql_ground_truth
python -m src.eval.ground_truth.generate_analysis_ground_truth
python -m src.eval.ground_truth.generate_visualization_ground_truth

# 2. Run everything: correctness (real agents + minimal baseline +
#    monolithic baseline, all 3 categories) + pipeline (latency + routing)
python -m src.eval.run_all

# 3. Report Agent -- separate, qualitative, not part of run_all
python -m src.eval.benchmarks.report_agent_benchmark

# 4. See results/eval/summary.csv and results/eval/report_agent_review.md
```

All three benchmark scripts (`correctness_benchmark.py`,
`pipeline_benchmark.py`, `report_agent_benchmark.py`) support resuming an
interrupted run without re-spending on already-completed work
(`--side`/`--categories`/`--sessions`).

### Results (55-question benchmark; primary run: Anthropic Claude Haiku 4.5)

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 20.0% | 86.7% | +80.0pp | +13.3pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Routing accuracy: 90.9%. Full latency, retry, and difficulty-tier
breakdowns, plus a complete question-by-question failure analysis (which
misses are genuine capability gaps vs. question-design ambiguities vs.
scoring-convention artifacts, including a real limitation found in the
evaluation's own scoring logic) are in
[`results_and_failure_analysis.md`](results_and_failure_analysis.md).

**Cross-model robustness** (evaluated on Groq `llama-3.3-70b`, Ollama
`llama3.1:8b`, and Anthropic `claude-haiku-4.5`): the real, specialized
system's correctness stays in an 80-100% band regardless of the
underlying model; the minimal baseline swings 20-77% depending on
provider. See §5 of the results document.

Both baselines use a deliberately minimal (no-tools) or identical
(same-tools, no-split) prompt respectively — isolating, separately,
whether tool access matters and whether decomposition itself matters.
See `docs/architecture.md` and the results document for full methodology.

---

## Testing

```bash
PYTHONPATH=. pytest tests/ -v
```

Runs entirely offline — no API key required (103 tests). For manual,
live-API checks (actual LLM calls), see `scripts/manual_check/`.

---

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — system architecture,
  execution flow, and the design decisions behind it, including two real
  production bugs found and fixed during evaluation.
- [`docs/development_log.md`](docs/development_log.md) — project
  implementation log (Milestones 1-13).
- [`results_and_failure_analysis.md`](results_and_failure_analysis.md)
  — full evaluation results, question-by-question failure
  classification, cross-model robustness analysis, and Report Agent
  qualitative review.
- [`MIGRATION.md`](MIGRATION.md) — record of the architecture restructure.

---

## Current Status

**Phase 1 (system implementation)** and **Phase 2 (evaluation)** are both
complete. The system includes the full multi-agent architecture,
centralized read-only database access, an automated offline test suite
(103 tests), and a complete empirical evaluation against two baselines
(minimal and monolithic), including routing accuracy, retry statistics,
and latency comparisons, cross-validated across three independent model
providers.

Remaining: the thesis write-up itself (Methodology, Results, and Failure
Analysis chapters), drawing directly on
`results_and_failure_analysis.md`.

---

## License

This project was developed as part of a Bachelor's Thesis at Universitat
Pompeu Fabra.
