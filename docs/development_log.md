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
live against the real dataset and a live model afterward: the filter fix
was checked against ground truth computed directly from SQL.

Test suite: 51 automated tests (`tests/`), entirely offline, no API keys
required. The two scripts that do require a live API key
(`check_llm_connection.py`, `check_router.py`) were moved to
`scripts/manual_check/` and are explicitly documented as not part of the
automated suite.

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

The complete architecture has been implemented and validated through
functional testing of all supported agent capabilities.

---

# Next Phase

Phase 2 focuses on the evaluation of the proposed architecture.

The evaluation will include:

- definition of a benchmark composed of representative analytical questions;
- establishment of suitable baseline approaches;
- quantitative evaluation of answer correctness;
- evaluation of routing accuracy;
- robustness analysis;
- latency and performance measurements;
- qualitative analysis of generated visualizations;
- systematic error analysis.
