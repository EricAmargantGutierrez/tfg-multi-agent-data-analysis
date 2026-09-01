# System Architecture

## Overview

The Multi-Agent Conversational Data Analysis System answers natural
language questions over the Superstore dataset. A LangGraph orchestrator
routes each question to one of four specialized MCP agents (SQL,
Analysis, Visualization, Report), which independently generate and
execute their own read-only queries against a shared SQLite database.

## Components

- **REPL** (`src/repl.py`) — command-line interface: receives questions,
  calls the orchestrator, prints answers, triggers the end-of-session
  report.
- **Orchestrator** (`src/orchestrator/`) — routes each question, invokes
  the selected agent over MCP, narrates the structured result, and
  accumulates conversation history.
- **Router** (`src/orchestrator/router.py`) — an LLM decides which agent
  handles a question; a keyword-based fallback (`keyword_route`) covers
  cases where the LLM is unavailable or returns garbage.
- **SQL / Viz / Analysis / Report Agents** (`src/agents/*/`) — each is an
  MCP server exposing one tool. Each has: `agent.py` (thin MCP wrapper),
  `engine.py` (the actual logic, directly unit-testable without FastMCP),
  and `prompts.py` (its system prompt).
- **Narrator** (`src/orchestrator/narrate.py`) — turns an agent's
  structured output into a natural-language response. Never touches the
  database itself.

## Who is allowed to touch the database

Three agents — SQL, Visualization, and Analysis — each independently
decide their own query. All three go through `src/core/db.py`, and
nothing else opens a connection to the database; every connection is
opened read-only, so a bug downstream cannot mutate the database
regardless of which agent triggered it. Analysis never lets the LLM
write raw SQL, it produces a structured plan (columns, filters, and
(for regression) a target / (for a t-test) a grouping column and two
group values to compare), validated as a Pydantic `AnalysisPlan`, and
`build_select` compiles it into a parameterized query.

## Protecting the LLM from its own agents' output size

`src/core/summarize.py` — a Viz Agent result with a large row list
(e.g. a 1,000-row scatter/boxplot/histogram result) being embedded
directly into an LLM prompt caused a `413 Request too large` error in
narration and a ~14,700-token single request in report generation. Both
`narrate.py` and `report/engine.py` now pass their input through
`summarize_large_rows()` first: any list of more than 15 row-shaped
items is replaced with a count + a 5-row sample before being sent to an
LLM.

## Robustness to missing/invalid data

`src/agents/analysis/statistics.py::_numeric()` drops any row containing
`NaN` in the selected numeric columns before computing anything, so
`compute_regression`/`compute_pca`/`compute_kmeans` (scikit-learn-based,
unlike the pandas-based scalar statistics, which already handle NaN
safely) can't crash on missing data. The project's dataset has zero
missing values, so this is a defensive fix, not something observed in
production.

## The t-test compares two groups, not two arbitrary columns

`compute_ttest` compares ONE numeric variable across TWO groups defined
by a categorical column (e.g. profit in the Consumer segment vs. the
Corporate segment), the standard meaning of a t-test. This was not the
original implementation: an earlier version compared two numeric
*columns* directly as independent samples (e.g. discount vs. profit),
which isn't a valid two-group hypothesis test since the two "samples"
were different variables on different scales. This was found during
evaluation, both as a documented limitation and as a demonstrated,
concrete problem, a generated session report described that flawed
test's result as indicating "a negative correlation," which a t-test
does not measure. Fixed by extending `AnalysisPlan` with `group_column`
and `group_values` fields (exactly two values required); the planner
LLM now names which column defines the two groups and which two values
to compare, and `compute_ttest` runs the real two-sample comparison.
Verified against the real database, at the unit level, the integration
level, and by re-generating the affected report and confirming the
misleading claim no longer appears.

## Conversation history — what it's actually used for

`SessionState.history` accumulates every turn's `(question, agent,
result)`. **Only the Report Agent consumes it.** Routing and narration
only ever see the current question, each turn is resolved independently.
This is a deliberate scope boundary matching the original proposal
(history feeds the Report Agent; it does not enable multi-turn reference
resolution).

## Execution Flow

1. User submits a question via the REPL.
2. `router.route()` picks an agent (LLM decision, keyword fallback if the
   LLM call fails or is invalid).
3. The orchestrator invokes that agent's MCP tool (in-memory transport by
   default, real stdio subprocesses via `TFG_MCP_TRANSPORT=stdio`).
4. The agent's `engine.py` runs its self-correcting loop
   (`src/core/retry.py`, shared by all three data agents): generate ->
   execute -> on failure, feed the error back to the LLM and retry, up to
   `max_retries`.
5. The structured result returns to the orchestrator.
6. `narrate.py` turns it into a natural-language response (large row
   lists summarized first, see above).
7. `(question, agent, result)` is appended to `history`.
8. When the session ends, the full history is handed to the Report Agent
   (also summarized first before serialization).

## Current Limitations

- Single SQLite database, single table.
- No multi-turn reference resolution.
- The Analysis Agent's filter language covers `= != > >= < <= LIKE IN
  BETWEEN` against real columns — enough for region/category/date-range
  filtering, not arbitrary boolean expressions.
- The t-test currently compares exactly two groups from one categorical
  column (e.g. two specific segments), it doesn't support comparing more
  than two groups (that would need ANOVA, a different test) or paired
  samples.
- Row-cap interaction with `ORDER BY`: when a query's result exceeds
  `src.core.db.MAX_ROWS = 1000`, *which* 1,000 rows are returned depends
  on sort order, two structurally equivalent queries with different (or
  absent) ordering can retrieve different row subsets from a table with
  more matching rows than the cap.
- The subprocess/self-correction sandbox model has no execution sandbox
  beyond SQL validation, no agent here executes arbitrary LLM-generated
  Python, which limits risk but also limits analytical flexibility to
  what `src/agents/analysis/statistics.py` implements.

## Future Extensions

- Multi-turn reference resolution using recent (not full) history.
- ANOVA / more-than-two-group comparisons.
- Additional statistical analyses / forecasting.
- Multi-table dataset (e.g. Olist) to stress-test JOIN handling.
- Full containerization (Docker Compose, one container per agent).
- Decentralized agent communication (Agents communicating directly with each other rather than through the orchestrator)
