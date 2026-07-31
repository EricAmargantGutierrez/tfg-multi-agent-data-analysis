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
  cases where the LLM is unavailable or returns garbage. Report intent is
  checked first, so a question that mentions both "report" and a
  statistical term still routes correctly.
- **SQL / Viz / Analysis / Report Agents** (`src/agents/*/`) — each is an
  MCP server exposing one tool. Each has: `agent.py` (thin MCP wrapper),
  `engine.py` (the actual logic, directly unit-testable without FastMCP),
  and `prompts.py` (its system prompt).
- **Narrator** (`src/orchestrator/narrate.py`) — turns an agent's
  structured output into a natural-language response. Never touches the
  database itself.

## Who is allowed to touch the database

**Design decision (deliberate deviation from the original proposal):**
three agents — SQL, Visualization, and Analysis — each independently
decide their own query rather than the orchestrator chaining SQL output
into the other agents. This is more decoupled than the original
single-SQL-Agent design, but it means "who can touch the DB" needs one
consistent answer, not three separate ones.

**The answer: all three go through `src/core/db.py`, and nothing else
opens a connection to the database.** That module:

- opens every connection read-only (`file:...?mode=ro`), so a bug
  downstream of it cannot mutate the database, regardless of which agent
  triggered it;
- is the single place schema introspection (`get_schema`,
  `get_valid_columns`) is defined, instead of being reimplemented per
  agent;
- offers two access patterns depending on the agent's needs:
  - `run_readonly_query` / `run_readonly_query_dicts` — for SQL and Viz,
    which let the LLM write complete, free-form SQL text (validated by
    `src/agents/safety.py` before execution);
  - `build_select` / `load_dataframe_readonly` — for Analysis, which
    never lets the LLM write raw SQL. Instead the LLM produces a
    structured plan (columns + filters + target), validated as a
    Pydantic `AnalysisPlan`, and `build_select` compiles it into a
    parameterized query — filter *values* are bound as SQL parameters,
    never string-interpolated.

## Protecting the LLM from its own agents' output size

`src/core/summarize.py` — added after a real production bug: a Viz Agent
result with a large row list (e.g. a 1,000-row scatter/boxplot/histogram
result, or an unaggregated SQL query) being embedded directly into an
LLM prompt caused a `413 Request too large` error in narration, and a
~14,700-token single request in report generation. Both
`src/orchestrator/narrate.py` and `src/agents/report/engine.py` now pass
their input through `summarize_large_rows()` first: any list of more
than 15 row-shaped items (dicts or lists — not short numeric lists like
PCA's `explained_variance_ratio` or regression's `coefficients`, which
pass through untouched) is replaced with a count + a 5-row sample before
being sent to an LLM. This is a single shared module, not two separate
fixes, specifically so a third occurrence of the same bug pattern can't
appear somewhere new.

## Robustness to missing/invalid data

`src/agents/analysis/statistics.py::_numeric()` drops any row containing
`NaN` in the selected numeric columns before computing anything.
Previously, `compute_regression`, `compute_pca`, and `compute_kmeans`
(which use scikit-learn, unlike `mean`/`median`/etc., which pandas
already handles NaN-safely) would crash outright on missing data. The
project's actual dataset has zero missing values, so this was never
observed in practice — the fix is defensive, protecting against a future
dataset refresh or a different, dirtier dataset.

## Conversation history — what it's actually used for

`SessionState.history` accumulates every turn's `(question, agent,
result)`. **Only the Report Agent consumes it.** Routing and narration
only ever see the current question — each turn is resolved independently.

This is a deliberate scope boundary, not a gap: the original proposal
specifies history being handed to the Report Agent at the end of a
session; it does not specify multi-turn reference resolution ("what
about last year?" referring to a previous answer). Supporting that would
require feeding recent history into every router/agent prompt, which adds
real cost, latency, and an open NLP problem (reference resolution)
outside the evaluation plan. It's listed under Future Extensions instead.

## Execution Flow

1. User submits a question via the REPL.
2. `router.route()` picks an agent (LLM decision, keyword fallback if the
   LLM call fails or is invalid).
3. The orchestrator invokes that agent's MCP tool (`mcp_clients.py`,
   in-memory transport by default, real stdio subprocesses via
   `TFG_MCP_TRANSPORT=stdio`).
4. The agent's `engine.py` runs its self-correcting loop
   (`src/core/retry.py`, shared by all three data agents): generate ->
   execute -> on failure, feed the error back to the LLM and retry, up to
   `max_retries`.
5. The structured result returns to the orchestrator.
6. `narrate.py` turns it into a natural-language response (skipped for
   error results and for the Report Agent's own success message, both of
   which are already human-readable; large row lists summarized first,
   see above).
7. `(question, agent, result)` is appended to `history`.
8. When the session ends, the full history is handed to the Report Agent
   (also summarized first before serialization).

## Current Limitations

- Single SQLite database, single table.
- No multi-turn reference resolution (see above).
- The Analysis Agent's filter language covers `= != > >= < <= LIKE IN
  BETWEEN` against real columns — enough for region/category/date-range
  filtering, not arbitrary boolean expressions.
- **`compute_ttest` compares two numeric *columns* directly as
  independent samples** (e.g. discount vs. profit), not two *groups* of
  the same variable split by a category (e.g. profit in Consumer vs.
  Corporate segment) — which is what "t-test" more naturally means in a
  BI context. This is a known, documented limitation, not an oversight —
  and evaluation confirmed it has a real, concrete consequence: a
  generated session report described this test's result as indicating a
  "correlation," which a t-test does not measure, producing a misleading
  claim in output a real user would read. Fixing this would mean
  extending `AnalysisPlan` with a group-by column, real scope work not
  taken on in this project.
- Row-cap interaction with `ORDER BY`: when a query's result exceeds
  `src.core.db.MAX_ROWS = 1000`, *which* 1,000 rows are returned depends
  on sort order — two structurally equivalent queries with different (or
  absent) ordering can retrieve different row subsets from a table with
  more matching rows than the cap. Observed during evaluation as a
  source of apparent scoring mismatches between otherwise-correct
  queries.
- The subprocess/self-correction sandbox model has no execution sandbox
  beyond SQL validation — no agent here executes arbitrary LLM-generated
  Python (unlike some designs), which limits risk but also limits
  analytical flexibility to what `src/agents/analysis/statistics.py`
  implements.

## Future Extensions

- Multi-turn reference resolution using recent (not full) history.
- Group-based t-test (two samples split by a categorical column, not two
  arbitrary columns).
- Additional statistical analyses / forecasting.
- Multi-table dataset (e.g. Olist) to stress-test JOIN handling.
- Full containerization (Docker Compose, one container per agent).
