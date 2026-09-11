# System Architecture

## Overview

The Multi-Agent Conversational Data Analysis System answers natural
language questions over the Superstore dataset. A LangGraph orchestrator
routes each question to one of four specialized MCP agents (Data Query,
Analysis, Visualization, Report). The first three independently generate
and execute their own read-only queries against a shared SQLite database;
the Report Agent works only from accumulated session history.

## Components

- **REPL** (`src/repl.py`) - the command-line interface: takes questions,
  calls the orchestrator, prints answers, and triggers the end-of-session
  report.
- **Orchestrator** (`src/orchestrator/`) - routes each question, calls
  the chosen agent over MCP, turns the structured result into text, and
  keeps track of the conversation history.
- **Router** (`src/orchestrator/router.py`) - an LLM decides which agent
  should handle a question. If the LLM call fails or returns something
  unusable, a keyword-based fallback (`keyword_route`) picks an agent
  instead.
- **Data Query / Viz / Analysis / Report Agents** (`src/agents/*/`) - each
  is an MCP server that exposes one tool. Each has `agent.py` (a thin MCP
  wrapper), `engine.py` (the real logic, which can be unit-tested
  directly without FastMCP), and `prompts.py` (its system prompt).
  Analysis also has `statistics.py` (the pandas/scikit-learn code).
- **Narrator** (`src/orchestrator/narrate.py`) - turns an agent's
  structured output into a normal-language answer. Never touches the
  database itself.

## Who is allowed to touch the database

Three agents - Data Query, Visualization, and Analysis - each work out
their own query. All three go through `src/core/db.py`, and nothing
else opens a connection to the database. Every connection is read-only,
so a bug further down the chain can't change the database no matter
which agent caused it. Analysis never lets the LLM write raw SQL - it
produces a structured plan instead (columns, filters, and for a
regression a target, or for a t-test a grouping column and the two
groups to compare). This plan is checked as a Pydantic `AnalysisPlan`,
and `build_select` turns it into a real, parameterized query.

Data Query and Visualization *do* let the LLM write raw SQL, so their
queries pass through `src/agents/safety.py::validate_sql_readonly`
before `db.py` runs them: it must start with `SELECT` or `WITH`, can't
contain a second statement after a `;`, and can't contain a write
keyword (`INSERT`, `UPDATE`, `DELETE`, `DROP`, ...). This is a keyword
check, not a full SQL parser - simple, but enough to block the one thing
that actually matters here (a write), and it's what raises the
`UnsafeSQLError` seen in `results_and_failure_analysis.md` §4.2.

## Protecting the LLM from its own agents' output size

`src/core/summarize.py` - putting a Viz Agent result with a big row list
(e.g. a 1,000-row scatter/boxplot/histogram) straight into an LLM prompt
caused a `413 Request too large` error in narration, and a single
~14,700-token request when generating a report. Both `narrate.py` and
`report/engine.py` now run their input through `summarize_large_rows()`
first: any list of more than 15 rows gets replaced with a count plus a
5-row sample before it's sent to an LLM.

## Robustness to missing/invalid data

`src/agents/analysis/statistics.py::_numeric()` drops any row with a
`NaN` in the selected numeric columns before computing anything. This
matters for the scikit-learn functions (`compute_regression`,
`compute_pca`, `compute_kmeans`), which would otherwise crash on missing
data - the pandas-based simple statistics already handle `NaN` safely on
their own. The Superstore dataset has no missing values at all, so this
is a safety net, not a fix for something that actually happened.

## The t-test compares two groups, not two arbitrary columns

`compute_ttest` compares ONE numeric variable across TWO groups, where
the groups come from a categorical column (e.g. profit in the Consumer
segment vs. the Corporate segment) - this is what a t-test is actually
for. `AnalysisPlan` has `group_column` and `group_values` (exactly two
values, checked by Pydantic): the planner LLM says which column defines
the groups and which two values to compare, and `compute_ttest` runs the
real two-group comparison.

An earlier version compared two numeric *columns* directly, treating
them as independent samples - that isn't a valid two-group test. This
was found and fixed during the evaluation; the full before/after is in
`results_and_failure_analysis.md` §3.5.

## Conversation history — what it's actually used for

`SessionState.history` keeps every turn's `(question, agent, result)`.
**Only the Report Agent reads it.** Routing and narration only ever see
the current question - each turn is handled on its own. This is a
deliberate choice, matching the original proposal: history feeds the
Report Agent, it doesn't let the system remember earlier turns while
answering a new question.

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

- One SQLite database, one table.
- No memory of earlier turns when answering a new question.
- The Analysis Agent's filters only support `= != > >= < <= LIKE IN
  BETWEEN` on real columns - enough for filtering by region, category,
  or a date range, but not any arbitrary condition.
- The t-test only compares exactly two groups from one categorical
  column (e.g. two specific segments). It can't compare more than two
  groups (that needs ANOVA, a different test) or paired samples.
- Row cap + `ORDER BY`: when a query's result has more than
  `src.core.db.MAX_ROWS = 1000` rows, *which* 1,000 come back depends on
  the sort order. Two queries that ask the same thing but sort
  differently (or don't sort at all) can return different rows if there
  are more matches than the cap.
- No agent here runs LLM-generated Python - the only safety check is on
  the SQL. That keeps things safe, but it also means the system can only
  do what `src/agents/analysis/statistics.py` already implements.

## Future Extensions

- Multi-turn reference resolution using recent (not full) history.
- ANOVA / more-than-two-group comparisons.
- Additional statistical analyses / forecasting.
- Multi-table dataset (e.g. Olist) to stress-test JOIN handling.
- Full containerization (Docker Compose, one container per agent).
- Decentralized agent communication (Agents communicating directly with each other rather than through the orchestrator)
