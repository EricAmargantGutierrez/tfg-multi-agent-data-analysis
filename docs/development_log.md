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
- Selected the main technologies: Python, LangGraph, FastMCP, SQLite, LangChain.

---

# Milestone 2 — Database

Implemented the data layer: dataset validation, automatic ingestion pipeline, database normalization, SQLite database creation.

---

# Milestone 3 — LLM Integration

Implemented a provider-independent LLM interface. Currently supported providers: Groq, Ollama, OpenAI, Anthropic. The active provider is selected via `TFG_MODEL` in project configuration.

---

# Milestone 4 — Multi-Agent Architecture

Implemented the complete multi-agent architecture composed of four independent MCP agents: SQL Agent, Analysis Agent, Visualization Agent, Report Agent. Each agent exposes a single MCP tool and has a clearly defined responsibility.

---

# Milestone 5 — LangGraph Orchestrator

Implemented the orchestration layer: LLM-based routing, MCP agent invocation, conversation state management, conversation history management, centralized natural-language narration of agent outputs.

---

# Milestone 6 — SQL Agent

Implemented natural language to SQL generation, SQLite schema awareness, read-only SQL validation, automatic retry after SQL generation or execution errors.

---

# Milestone 7 — Analysis Agent

Implemented a dedicated statistical analysis agent: descriptive statistics, correlation, covariance, independent t-tests, linear regression, PCA, K-Means clustering. The agent retrieves data from SQLite, computes using Python scientific libraries, and returns structured results.

---

# Milestone 8 — Visualization Agent

Implemented automatic chart generation from natural language requests: automatic SQL generation, data retrieval, Matplotlib chart generation, figure storage in `results/`.

---

# Milestone 9 — Report Agent

Implemented automatic generation of Markdown reports summarizing each interaction session.

---

# Milestone 10 — Interactive Interface

Implemented a command-line conversational interface (REPL) allowing users to interact with the complete system, including automatic session report generation.

---

# Milestone 11 — Architecture Cleanup & Correctness Fixes

Reviewed the Phase 1 implementation before moving to evaluation. Structural changes: consistent `agent.py` + `engine.py` + `prompts.py` layout per agent; centralized all SQLite access in `src/core/db.py` (previously inconsistent read-only/read-write access across agents); extracted the shared self-correction loop (`src/core/retry.py`) and JSON-parsing helper (`src/core/llm_json.py`); introduced Pydantic models (`src/models/schemas.py`).

Correctness fixes: Analysis Agent filtering (previously no `WHERE` clause was possible at all — any filtered question silently computed over the entire table); router keyword ordering bug; SQL injection defense-in-depth (structural rejection of stacked statements); ingestion date-handling hardening; removed three stale test files referencing code that no longer existed.

Test suite: 51 automated tests, offline, at the end of this milestone.

---

# Milestone 12 — First Evaluation Round (Groq)

Designed and executed the initial empirical evaluation: 55 questions (30 SQL, 15 Analysis, 10 Visualization) against a minimal single-agent baseline, on Groq `llama-3.3-70b`.

A real bug was found and fixed via this process: `compute_regression` selected its prediction target by column-list position rather than an explicit field — the live planner's natural column ordering silently swapped the regression target, producing a low-r² wrong answer with no error. Fixed by adding an explicit `target` field to `AnalysisPlan`.

Results: SQL 100% vs. baseline 33.3% (+66.7pp); Analysis 100% vs. baseline 20.0% (+80.0pp); Visualization 100% vs. baseline 80.0% (+20.0pp); routing accuracy 90.9%. Detailed failure analysis found that most of the SQL baseline's apparent gap was a prompt-discipline artifact (missing output-value convention), not a raw capability gap, while Analysis's gap was genuine and structural (SQLite cannot compute PCA/K-Means/regression). Test suite: 78 tests.

---

# Milestone 13 — Evaluation Consolidation, New Baseline, Bug Fixes, Multi-Provider Final Run

Substantial follow-up work before treating the evaluation as complete.

## Evaluation harness consolidation

The original evaluation harness had grown to 7 separate benchmark scripts,
with real duplication: routing accuracy and pipeline latency were each
re-asking the same 55 questions independently, both through
`graph.answer()`. Consolidated to 3 files:
- `correctness_benchmark.py` — replaces 5 previous files (per-category
  correctness scripts + the baseline runner), now also runs the new
  monolithic side (see below).
- `pipeline_benchmark.py` — merges the former separate routing-accuracy
  and pipeline-latency scripts into one pass, since both were measuring
  properties of the same `graph.answer()` call.
- `report_agent_benchmark.py` — unchanged in scope, hardened for
  resumability (see below).

## A second, stronger baseline: the monolithic agent

`src/eval/baselines/monolithic_agent.py` — a single agent with access to
all three real capabilities (SQL execution, statistics, chart rendering),
deciding for itself which to use, versus the four specialized agents +
router. This isolates a different question than the minimal baseline:
not "does having tools help at all" but "does splitting those tools
across separate agents add value, beyond just having them available to
one agent." Built to reuse the exact same execution code as the real
agents (`src.core.db`, `statistics.py`, `viz.engine.render()` — imported
directly, not reimplemented).

**A methodological flaw was found and corrected during this work**: the
first version of the monolithic agent's system prompt was a hand-written
206-word summary of the specialized agents' rules, versus their real
combined ~845 words — missing entire sections (SQL's worked examples,
Viz's warning against unsupported date functions, Analysis's filter
examples). This would have confounded "architecture" with "less detailed
prompting" in any resulting gap. Fixed by importing the three real system
prompts verbatim and concatenating them, so the monolithic agent has
provably the same instructions as the real agents, differing only in
architecture.

## Two real production bugs found and fixed

1. **Token-limit bug in narration and report generation** (see
   `docs/architecture.md`, "Protecting the LLM from its own agents'
   output size"). Found via a real `413 Request too large` error on a
   1,000-row scatter chart result during evaluation, and independently
   via a ~14,700-token single request during report generation for a
   session containing a large-row chart. Fixed with a shared
   `src/core/summarize.py`, used by both `narrate.py` and
   `report/engine.py`.
2. **NaN crash in `compute_regression`/`compute_pca`/`compute_kmeans`**
   (see `docs/architecture.md`, "Robustness to missing/invalid data").
   Found while building the Analysis ground-truth generator against a
   dataset with missing values (not the project's actual dataset, which
   has none — a defensive fix for future robustness).

## Benchmark resumability

`correctness_benchmark.py`, `pipeline_benchmark.py`, and
`report_agent_benchmark.py` all gained `--categories`/`--side`/
`--sessions` flags with safe merge logic: re-running only the
incomplete portion preserves already-completed results on disk instead
of overwriting the whole file. Added after repeatedly losing partial
progress to rate limits and infrastructure interruptions during this
phase. Also added: automatic stop after 3 consecutive failures (instead
of grinding through a fully-exhausted quota), per-pass warm-up calls
(each of the 9 correctness passes, 3 pipeline categories, and 5 report
sessions independently exercises a cold model/prompt-shape cost before
being timed for real — a single global warm-up call was found, by
direct measurement, to be insufficient once more than one genuinely
different call shape was involved).

## Multi-provider evaluation journey

The complete evaluation (all 4 dimensions: correctness x3 sides,
pipeline/routing, Report Agent) was run to completion on three different
providers over the course of this milestone:

- **Groq** (`llama-3.3-70b`) — completed correctness runs; pipeline runs
  repeatedly interrupted by free-tier daily/per-minute token limits.
- **Ollama** (`llama3.1:8b`, local) — completed correctness runs (agent/
  baseline/monolithic, all 3 categories). Pipeline runs failed
  repeatedly: isolated router testing showed the local 8B model
  genuinely, reproducibly misrouting unambiguous SQL questions to the
  Analysis Agent (a real model-capability limitation, not a code
  defect — confirmed via the same router logic that performs correctly
  on the other two providers) and separately, sustained local inference
  caused WSL memory exhaustion and likely thermal throttling, both
  legitimate, reportable infrastructure limitations of local-model
  deployment.
- **Anthropic** (`claude-haiku-4.5`) — the only provider on which all
  four dimensions completed cleanly on a single, consistent model. Used
  as the primary reported dataset.

## Final results (Anthropic, primary dataset)

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 20.0% | 86.7% | +80.0pp | +13.3pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Routing accuracy: 90.9%. Retry rate: 0% (now confirmed across all three
providers — a robust finding, not missing data).

A full failure analysis was performed for every non-correct result
across all runs (see `results_and_failure_analysis.md`). Two findings
stand out:

1. **A real limitation in the evaluation's own scoring**, not the
   system: the baseline scorer assumes correlation/covariance are
   structurally inexpressible in one SQL query; Claude's baseline
   derived the correct closed-form Pearson formula manually and matched
   the real system's value almost exactly, but was scored incorrect by
   design regardless.
2. **Cross-provider robustness**: the real, specialized-agent system's
   correctness stays in an 80-100% band regardless of the underlying
   model (Ollama 8B, Groq 70B, Claude Haiku); the baseline swings far
   more widely (20-77%) depending on provider. The architecture's value
   includes making the system robust to model choice, not only raw
   capability uplift on any single model.

## Report Agent — qualitative evaluation completed

5 curated multi-question sessions run through the real orchestrator,
rated by hand (accuracy, completeness, no-fabrication, fluency; 1-5
each). Mean: accuracy 3.4/5, completeness 5.0/5, no-fabrication 3.4/5,
fluency 5.0/5. Fluency and completeness are consistently strong. Real
issues found: an invented, statistically meaningless metric in one
session (direct violation of the agent's own "do not invent
information" instruction); genuine arithmetic errors and a cross-turn
misattribution in another; and, most significantly, a session where the
report described a t-test result as indicating "correlation" — which a
t-test does not measure — independently confirming the `compute_ttest`
limitation documented in `docs/architecture.md` produces a real,
misleading claim in output a user would read and trust, not merely a
theoretical concern.

## Test suite

Grew to 103 automated tests, still entirely offline, including tests for
the monolithic agent (run against the real database with dynamically
computed expected values, not hardcoded numbers), the shared summarizer,
the report engine's token-limit fix, and the warm-up helper.

---

# Phase 2 Completed

The empirical evaluation is complete: benchmark, ground truth, three-way
correctness comparison, routing/latency measurement, retry data, and
qualitative Report Agent review, cross-validated across three model
providers. Full results and failure analysis in
`results_and_failure_analysis.md`.

# Remaining Work

- Thesis write-up: Methodology, Results, and Failure Analysis chapters,
  drawing directly on `results_and_failure_analysis.md` and the
  per-question result files in `results/eval/`.
