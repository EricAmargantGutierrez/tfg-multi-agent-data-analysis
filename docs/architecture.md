# System Architecture

## Overview

This system answers natural language questions about the Superstore
dataset. A LangGraph orchestrator sends each question to one of four
agents: Data Query, Analysis, Visualization, or Report. The first three
agents each build and run their own read-only query against one shared
SQLite database. The Report Agent is different - it never touches the
database, it only reads what happened earlier in the conversation.

## Components

- **REPL** (`src/repl.py`) - the command-line interface: it takes
  questions, calls the orchestrator, prints the answers, and starts the
  end-of-session report.
- **Orchestrator** (`src/orchestrator/`) - routes each question, calls
  the chosen agent over MCP, turns the structured result into text, and
  keeps track of the conversation history.
- **Router** (`src/orchestrator/router.py`) - an LLM decides which agent
  should handle a question. If that LLM call fails or gives back
  something unusable, a backup (`keyword_route`) picks an agent by
  looking for keywords instead.
- **Data Query / Viz / Analysis / Report Agents** (`src/agents/*/`) -
  each one is an MCP server that exposes one tool. Each has `agent.py`
  (a small MCP wrapper), `engine.py` (the real logic, which can be
  tested directly without FastMCP), and `prompts.py` (its system
  prompt). Analysis also has `statistics.py` (the pandas/scikit-learn
  code).
- **Narrator** (`src/orchestrator/narrate.py`) - turns an agent's
  structured output into a normal-language answer. It never touches the
  database itself.

## Who is allowed to touch the database

Three agents - Data Query, Visualization, and Analysis - each build
their own query. All three go through `src/core/db.py`, and nothing
else opens a connection to the database. Every connection is read-only,
so a bug anywhere else in the code cannot change the database, no
matter which agent caused it. Analysis never lets the LLM write raw
SQL - instead, it produces a plan (columns, filters, and for a
regression a target column, or for a t-test a grouping column and the
two groups to compare). This plan is checked as a Pydantic
`AnalysisPlan`, and `build_select` turns it into a real query. The
query is "parameterized," which means the actual values are passed in
safely and are never pasted directly into the SQL text.

Data Query and Visualization *do* let the LLM write raw SQL, so their
queries pass through `src/agents/safety.py::validate_sql_readonly`
before `db.py` runs them: the query must start with `SELECT` or `WITH`,
it can't contain a second statement after a `;`, and it can't contain a
write keyword (`INSERT`, `UPDATE`, `DELETE`, `DROP`, ...). This is a
simple keyword check, not a full SQL parser, but it's enough to block
the one thing that actually matters here (a write). It's also what
raises the `UnsafeSQLError` you can see in
`results_and_failure_analysis.md` §4.2.

## Protecting the LLM from its own agents' output size

`src/core/summarize.py` - if I put a Viz Agent result with a lot of
rows (say, a 1,000-row scatter plot, boxplot, or histogram) straight
into an LLM prompt, it caused a `413 Request too large` error when
narrating the answer, and one very large request (about 14,700 tokens)
when writing a report. Both `narrate.py` and `report/engine.py` now run
their input through `summarize_large_rows()` first: any list of more
than 15 rows gets replaced with a count plus a 5-row sample before it's
sent to an LLM.

## Robustness to missing/invalid data

`src/agents/analysis/statistics.py::_numeric()` removes any row with a
missing value (`NaN`) in the chosen numeric columns before computing
anything. This is needed for the scikit-learn functions
(`compute_regression`, `compute_pca`, `compute_kmeans`), which would
otherwise crash on missing data. The simple pandas statistics already
handle `NaN` safely on their own, so they don't need this. The
Superstore dataset has no missing values at all, so this is an extra
safety check, not a fix for a problem that actually happened.

## The t-test compares two groups, not two random columns

`compute_ttest` compares ONE numeric variable across TWO groups, where
the groups come from a categorical column (e.g. profit in the Consumer
segment vs. the Corporate segment). This is what a t-test is actually
for. `AnalysisPlan` has `group_column` and `group_values` (exactly two
values, checked by Pydantic): the planner LLM says which column
defines the groups and which two values to compare, and `compute_ttest`
runs the real two-group comparison.

An earlier version compared two numeric *columns* directly, as if they
were two separate groups - that isn't a valid two-group test. I found
this bug and fixed it during the evaluation; the full before-and-after
is in `results_and_failure_analysis.md` §3.5.

## Conversation history — what it's actually used for

`SessionState.history` keeps every turn's `(question, agent, result)`.
**Only the Report Agent reads it.** Routing and narration only ever see
the current question - each turn is handled on its own. I made this
choice on purpose, to match my original project proposal: history is
only there to feed the Report Agent, it doesn't let the system remember
earlier turns while answering a new question.

## Execution Flow

1. The user submits a question through the REPL.
2. `router.route()` picks an agent (an LLM decision, with a keyword
   backup if the LLM call fails or gives back something invalid).
3. The orchestrator calls that agent's MCP tool (in-memory by default,
   real stdio subprocesses if `TFG_MCP_TRANSPORT=stdio` is set).
4. The agent's `engine.py` runs its self-correcting loop
   (`src/core/retry.py`, shared by all three data agents): generate ->
   run -> if it fails, send the error back to the LLM and try again, up
   to `max_retries` times.
5. The structured result goes back to the orchestrator.
6. `narrate.py` turns it into a natural-language response (large row
   lists are summarized first, as above).
7. `(question, agent, result)` is added to `history`.
8. When the session ends, the full history is handed to the Report
   Agent (also summarized first, before being turned into JSON).

## What each agent actually does

The Execution Flow above looks the same for every agent from the
outside (the router picks it, MCP calls it, it runs, the result comes
back). This section looks inside each agent's own box: what it gets as
input, the steps it runs, and exactly what it can and can't do.

### Data Query Agent

- **Input:** the question, plus the database schema (table and column
  names).
- **Steps:** the LLM writes one plain SQL query. That query goes
  through `src/agents/safety.py::validate_sql_readonly` (must be
  `SELECT`/`WITH`, no second statement, no write keyword), then it runs
  for real against the database. If it fails, the error message goes
  back to the LLM and it tries again, up to 3 times
  (`src/core/retry.py`).
- **Can do:** anything you can answer with one read-only SQL query -
  totals, averages, counts, filtering, sorting, grouping.
- **Can't do:** anything that needs more than plain SQL (a real
  statistical test, a chart) - those go to the other two agents.

### Analysis Agent

- **Input:** the question, plus the schema.
- **Steps:** the LLM never writes SQL here. It returns a JSON plan
  instead: which analysis to run, which columns to use, an optional
  filter, and (only for regression) a target column, or (only for a
  t-test) a group column and the two groups to compare. This plan is
  checked with Pydantic (`AnalysisPlan`), turned into a safe SQL query
  that fetches just the needed columns, loaded into a pandas DataFrame,
  and then the chosen function runs on that data. Same retry loop as
  Data Query if something fails.
- **Can do:** exactly 15 functions, all in `statistics.py`: mean,
  median, mode, variance, std, min, max, count, describe, correlation,
  covariance, a two-group t-test, linear regression, PCA, and K-Means.
- **Can't do:** anything not on that list (e.g. ANOVA, forecasting), or
  a t-test across more than two groups. It never writes or runs its own
  code - it only picks from this fixed list.

### Visualization Agent

- **Input:** the question, plus the schema.
- **Steps:** the LLM decides *what* to plot - chart type, the SQL to
  get the data, title and axis labels - as a JSON "chart spec"
  (`ChartSpec`). The system runs that SQL, then fixed, trusted
  Matplotlib code (not the LLM) actually draws the chart and saves it
  as a PNG file. Correctness is checked against the data behind the
  chart, not by reading the image. Same retry loop on failure.
- **Can do:** 6 chart types - bar, line, scatter, pie, histogram,
  boxplot. Rows with a missing (`NULL`) value in a plotted column are
  dropped instead of crashing the chart.
- **Can't do:** any chart type outside that list of 6.

### Report Agent

- **Input:** the *entire* conversation history so far - every earlier
  turn's question, which agent handled it, and its result (summarized
  first if any turn has a big row list, see above).
- **Steps:** one single LLM call - there is no retry loop here. If the
  call fails, report generation just fails (`ok: False`); there's no
  syntax error to fix and retry the way there is for the other three
  agents. The LLM writes a full report (Executive Summary, Questions
  Asked, Key Findings, Conclusions) as one block of text, saved to a
  file.
- **Can do:** turn a whole conversation into one readable report.
- **Can't do:** check any of it. It never runs its own SQL, analysis,
  or chart - it only sees what the other agents already returned. So if
  an earlier turn was wrong (or an agent quietly used a different
  column instead of a missing one), the Report Agent has no way to
  catch that, and it can end up repeating the mistake, or even making
  it sound fine. See `results_and_failure_analysis.md` §4.2 for real
  examples of this.

## Current Limitations

- One SQLite database, one table.
- No memory of earlier turns when answering a new question.
- The Analysis Agent's filters only support `= != > >= < <= LIKE IN
  BETWEEN` on real columns - enough for filtering by region, category,
  or a date range, but not any condition you could think of.
- The t-test only compares exactly two groups from one categorical
  column (e.g. two specific segments). It can't compare more than two
  groups (that needs ANOVA, a different test), and it can't handle
  paired samples (two measurements on the same subject).
- Row cap + `ORDER BY`: when a query's result has more than
  `src.core.db.MAX_ROWS = 1000` rows, *which* 1,000 rows come back
  depends on the sort order. Two queries that ask the same thing but
  sort differently (or don't sort at all) can return different rows if
  there are more matches than the cap.
- No agent here runs LLM-written Python code - the only safety check is
  on the SQL. That keeps things safe, but it also means the system can
  only do what `src/agents/analysis/statistics.py` already has built
  in.

## Future Extensions

- Understanding references to earlier turns (like "that region")
  using only the last few turns, not the whole history.
- ANOVA and other comparisons across more than two groups.
- More statistical analyses, or forecasting.
- A dataset with more than one table (e.g. Olist), to test how well the
  system handles JOINs.
- Running everything in Docker containers, one container per agent
  (using Docker Compose).
- Agents talking to each other directly, instead of always going
  through the orchestrator.
