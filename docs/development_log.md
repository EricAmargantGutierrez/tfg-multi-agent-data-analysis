# Development Log

**Project:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Project Objective

Develop a conversational system capable of answering natural language questions over structured datasets using a modular multi-agent architecture based on the Model Context Protocol (MCP).

The project combines Large Language Models, LangGraph orchestration, SQLite databases, and specialized agents for SQL querying, statistical analysis, visualization, and report generation.

---

# Milestone 1 — Project Initialization

Completed tasks:

- Defined the project objectives.
- Selected the Superstore dataset as the experimental dataset.
- Designed the initial project structure.
- Selected the main technologies:
  - Python
  - LangGraph
  - FastMCP
  - SQLite
  - LangChain

---

# Milestone 2 — Database

Implemented the data layer.

Completed tasks:

- Dataset validation.
- Automatic ingestion pipeline.
- Database normalization.
- SQLite database creation.

---

# Milestone 3 — LLM Integration

Implemented a provider-independent LLM interface.

Currently supported providers:

- Groq
- Ollama
- OpenAI
- Anthropic

The active provider can be selected through the project configuration.

---

# Milestone 4 — Multi-Agent Architecture

Implemented the complete multi-agent architecture composed of four independent MCP agents.

- SQL Agent
- Analysis Agent
- Visualization Agent
- Report Agent

Each agent exposes a single MCP tool and has a clearly defined responsibility.

---

# Milestone 5 — LangGraph Orchestrator

Implemented the orchestration layer.

Completed tasks:

- LLM-based routing.
- MCP agent invocation.
- Conversation state management.
- Conversation history management.
- Centralized natural-language narration of agent outputs.

---

# Milestone 6 — SQL Agent

Implemented:

- Natural language to SQL generation.
- SQLite schema awareness.
- Read-only SQL validation.
- Automatic retry after SQL generation or execution errors.

---

# Milestone 7 — Analysis Agent

Implemented a dedicated statistical analysis agent.

Completed features:

- Descriptive statistics.
- Correlation analysis.
- Covariance computation.
- Independent t-tests.
- Linear regression.
- Principal Component Analysis (PCA).
- K-Means clustering.

The agent retrieves the required data from SQLite, performs the requested computation using Python scientific libraries, and returns structured results to the orchestrator.

---

# Milestone 8 — Visualization Agent

Implemented automatic chart generation from natural language requests.

Completed tasks:

- Automatic SQL generation.
- Data retrieval.
- Matplotlib chart generation.
- Figure storage in the `results/` directory.

---

# Milestone 9 — Report Agent

Implemented automatic generation of Markdown reports summarizing each interaction session.

---

# Milestone 10 — Interactive Interface

Implemented a command-line conversational interface (REPL) allowing users to interact with the complete system.

The REPL supports conversational sessions and automatically generates a session report when the interaction finishes.

---

# Milestone 11 — Architecture Cleanup & Correctness Fixes

A review of the Phase 1 implementation surfaced several issues that were
addressed before moving to Phase 2 (evaluation), since correctness bugs
found during evaluation would be far more expensive to trace back.

Structural changes:

- Reorganized each agent into a consistent `agent.py` (MCP wrapper) +
  `engine.py` (core logic) + `prompts.py` (system prompt) layout. The
  Report Agent previously kept its logic inline in the MCP wrapper; it
  now follows the same pattern as the other three.
- Centralized all SQLite access into a single module (`src/core/db.py`).
  Previously, three agents each opened their own connection
  independently and inconsistently: the SQL Agent opened the database
  read-only, but the Visualization and Analysis Agents opened it
  read-write. All three now go through the same read-only chokepoint.
- Extracted the self-correcting retry loop (previously duplicated,
  nearly identically, in all three data agents) into a single shared
  helper (`src/core/retry.py`).
- Extracted the "parse LLM JSON output" logic (previously duplicated in
  two agents and reimplemented a third time, differently, in the router)
  into a single shared helper (`src/core/llm_json.py`).
- Introduced Pydantic models (`src/models/schemas.py`) for
  LLM-produced structured objects (analysis plans, chart specs, routing
  decisions), replacing hand-rolled manual key checks.

Correctness fixes:

- **Analysis Agent filtering.** The Analysis Agent could previously only
  select whole columns with no `WHERE` clause, so any question with a
  condition in it (e.g. "average profit in the West region") silently
  computed over the entire table and returned a confidently wrong
  answer with no error. Fixed by adding a `filters` field to the
  planner's output schema, compiled into a parameterized SQL `WHERE`
  clause (filter values are bound as SQL parameters, never
  string-interpolated).
- **Router keyword ordering.** The keyword-based routing fallback
  checked for statistical terms before checking for report intent, so a
  question like "generate a report showing the average profit" was
  misrouted to the Analysis Agent instead of the Report Agent. Fixed by
  checking report intent first.
- **SQL injection defense-in-depth.** The read-only SQL guard relied on
  a forbidden-keyword scan to incidentally catch stacked statements
  (e.g. `SELECT 1; DROP TABLE orders` was blocked only because `DROP`
  happens to be a forbidden keyword). Added an explicit check that
  rejects any additional statement by structure.
- **Ingestion date handling.** Hardened `src/ingest.py` with an explicit
  date format (`%m/%d/%Y`) instead of relying on pandas to infer it, and
  added a post-ingestion sanity assertion that a year-grouped date query
  returns real, non-null totals before ingestion is allowed to succeed.
- Removed three stale test files (`test_database.py`, `test_settings.py`,
  `test_sql_agent.py`) that referenced classes and modules no longer
  present in the codebase (`DatabaseManager`, `Settings.llm_provider`,
  a `SQLAgent` class) — confirmed via `ImportError`/`AttributeError`
  before removal, not assumed.

The full file-by-file rationale is recorded in `MIGRATION.md`. The
restructured system was verified end-to-end (stub LLM + real SQLite +
real FastMCP memory transport) before being merged, and confirmed again
live against the real dataset and a live model afterward.

Test suite: 51 automated tests (`tests/`), entirely offline, no API keys
required, at the end of this milestone.

---

# Phase 1 Completed

Phase 1 of the project has been successfully completed, including the
Milestone 11 cleanup above.

The implemented system includes:

- complete multi-agent architecture;
- MCP-based communication;
- LangGraph orchestration;
- conversational interaction;
- LLM-based routing;
- SQL generation and execution;
- statistical analysis and machine learning, including column-level filtering;
- automatic visualization generation;
- centralized natural-language response generation;
- automatic session report generation;
- support for multiple LLM providers;
- centralized, read-only database access;
- an automated, offline test suite.

---

# Milestone 12 — Evaluation

Designed and executed the full empirical evaluation of the multi-agent
architecture against a single-agent baseline, per the evaluation plan in
the project proposal.

## Benchmark design

- **55 questions** across three categories: 30 SQL, 15 Analysis, 10
  Visualization, each spanning easy/medium/hard difficulty. The SQL set
  was written first; Analysis and Visualization sets were added to cover
  every capability implemented in `statistics.py` and every chart type
  supported by the Visualization Agent.
- **Ground truth computed by execution, never by LLM.** SQL and
  Visualization ground truth is generated by running hand-written
  reference SQL directly against the database. Analysis ground truth is
  generated by running a hand-written reference plan (columns + filters
  + target) through the same trusted, deterministic `statistics.py`
  functions the real agent uses — never by asking an LLM what the
  "right" answer is, which would be circular.
- **Scoring is on structured output only, never narrated prose** — every
  agent already returns structured data (rows, or a statistics result
  dict) before the narration step touches it, so comparison is a plain
  numeric-tolerance / order-independent check, with no ambiguity from
  how an LLM might phrase a correct answer.
- **Baseline design.** The same LLM, given the schema and the question,
  with a deliberately minimal, generic prompt ("write one SQL query") —
  not the real agents' tuned prompts. This isolates the value of the
  full agent architecture (specialized prompts + retry + real Python
  execution for statistics) rather than just measuring "does a better
  prompt help."
- **Routing accuracy measured independently** of answer correctness: for
  every question, `router.route()` is checked against the question's
  expected agent, separately from whether the chosen agent then answered
  correctly.

## A real bug found and fixed via this process

Building the evaluation surfaced a genuine correctness bug, not just a
benchmark artifact: `compute_regression` selected the prediction target
(y) by taking whatever column happened to be *last* in the planner's
column list — an implicit convention the LLM had no way of knowing.
Asked to "predict profit from sales, discount, and quantity," the live
planner naturally listed columns in question order (profit first), which
silently swapped the regression target and produced a low-r² result with
no error. Fixed by adding an explicit `target` field to `AnalysisPlan`
(Pydantic-validated, required for `regression`), so the target is named,
not inferred from position. Verified against the exact failure scenario
before and after the fix, and confirmed the retry loop correctly
self-corrects if the LLM forgets to include it.

## Results

| Category | System correctness | Baseline correctness | Architecture value |
|---|---|---|---|
| SQL | 100% (30/30) | 33.3% | +66.7pp |
| Analysis | 100% (15/15) | 20.0%\* | +80.0pp |
| Visualization | 100% (10/10) | 80.0% | +20.0pp |

Routing accuracy across all 55 questions: **90.9%** (5 misroutes, all
between `sql` and `analysis` on questions with ambiguous phrasing).

\* Baseline correctness on the Analysis set varied slightly between two
runs (26.7% and 20.0%) taken hours apart, using the same 15 questions and
the same model. This reflects the inherent non-determinism of live LLM
sampling, not a measurement error — the real Analysis Agent's own
correctness was stable at 93–100% across the same runs. Retry rate was
0% across every category in this evaluation run: the self-correction
loop was never exercised by the model used (Groq `llama-3.3-70b`), which
means retry effectiveness is not yet empirically measured and would need
either harder questions or a weaker model to observe.

Concrete, characterized baseline failure modes (not just "it got it
wrong"): missing SQLite functions (`STDDEV`, `VARIANCE`, `CORR`,
`QUANTILE` do not exist), a genuine SQL syntax error attempting nested
aggregates for covariance, no attempt at dimensionality reduction for
PCA (returned raw columns unchanged), and for K-Means, a hardcoded
`CASE WHEN` rule dressed up as clustering rather than a real
unsupervised algorithm — a "plausible but conceptually wrong" failure,
notably different from a clean SQL error.

## Test suite

Grew to 78 automated tests, still entirely offline, including regression
tests for the routing bug, the analysis filter fix, and the new
regression-target validation.

---

# Phase 2 Completed

The empirical evaluation is complete: benchmark, ground truth, baseline,
scoring, and full results are in `src/eval/` and `results/eval/`.

# Remaining Work

- Qualitative rating (1–5 fluency/usefulness) on a sample of narrated
  answers — a manual step by design, not automated.
- Thesis write-up: Evaluation Methodology, Results, and Failure Analysis
  chapters, drawing on `results/eval/summary.csv` and the per-question
  result files.
