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
  statistical term (e.g. "generate a report showing the average profit")
  still routes correctly.
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
    structured plan (columns + filters), validated as a Pydantic
    `AnalysisPlan`, and `build_select` compiles it into a parameterized
    query — filter *values* are bound as SQL parameters, never
    string-interpolated.

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
   which are already human-readable).
7. `(question, agent, result)` is appended to `history`.
8. When the session ends, the full history is handed to the Report Agent.

## Current Limitations

- Single SQLite database, single table.
- No multi-turn reference resolution (see above).
- The Analysis Agent's filter language covers `= != > >= < <= LIKE IN
  BETWEEN` against real columns — enough for region/category/date-range
  filtering, not arbitrary boolean expressions.
- The subprocess/self-correction sandbox model has no execution sandbox
  beyond SQL validation — no agent here executes arbitrary LLM-generated
  Python (unlike some designs), which limits risk but also limits
  analytical flexibility to what `src/agents/analysis/statistics.py`
  implements.

## Future Extensions

- Multi-turn reference resolution using recent (not full) history.
- Additional statistical analyses / forecasting.
- Multi-table dataset (e.g. Olist) to stress-test JOIN handling.
- Full containerization (Docker Compose, one container per agent).
