# Migration notes: old structure -> this restructure

Apply this on top of your actual repo (this bundle was built and verified
in an isolated sandbox, not against your live `.env`/keys).

## 1. Files to delete
- `src/database/` (entire folder — contents moved, see table below)
- `src/analysis/` (entire folder — moved into `src/agents/analysis/`)
- `tests/test_database.py` — imports `DatabaseManager`, which doesn't
  exist anywhere in the current code. Confirmed via `ImportError` when run.
- `tests/test_settings.py` — reads `settings.llm_provider` /
  `settings.llm_model`, neither of which exists on `Settings` (it only
  has `default_model`). Confirmed via `AttributeError` when run.
- `tests/test_sql_agent.py` — imports a `SQLAgent` class that doesn't
  exist (`sql_agent.py` only exports `mcp` and the `run_sql` tool
  function). Confirmed via `ImportError` when run.

## 2. Files that moved (logic preserved, plus the fixes noted)
| Old path | New path | What changed |
|---|---|---|
| `src/database/engine.py` | `src/ingest.py` | explicit `%m/%d/%Y` date format instead of inference; added post-ingestion sanity assertion (year-grouped query must return real numbers); row-count check loosened from exact `== 9994` to a sanity range |
| `src/database/sql_engine.py` | `src/agents/sql/engine.py` + `src/core/db.py` | schema/query logic now shared via `core/db.py`; system prompt moved to `prompts.py` |
| `src/database/chart_engine.py` | `src/agents/viz/engine.py` | now opens DB read-only (was read-write); validates the LLM's chart spec with `ChartSpec` instead of manual key checks; retry loop now uses the shared helper |
| `src/analysis/analysis_engine.py` | `src/agents/analysis/engine.py` | behavior change, not just a move -- added `filters` support (see #3 below); now opens DB read-only (was read-write); validated with `AnalysisPlan` |
| `src/analysis/statistics.py` | `src/agents/analysis/statistics.py` | unchanged |
| `src/agents/sql_agent.py` | `src/agents/sql/agent.py` | now a thin wrapper only |
| `src/agents/viz_agent.py` | `src/agents/viz/agent.py` | now a thin wrapper only |
| `src/agents/analysis_agent.py` | `src/agents/analysis/agent.py` | now a thin wrapper only |
| `src/agents/report_agent.py` | `src/agents/report/agent.py` + `src/agents/report/engine.py` | logic extracted into `engine.py` (was inline in the MCP wrapper -- the only one of the four that wasn't) |

## 3. The actual bug fix (not just a refactor)
`analysis_engine.build_sql` previously could only ever produce
`SELECT {columns} FROM orders` -- no `WHERE`, no `GROUP BY`, ever. Any
analysis question with a condition in it ("average profit in the West
region") silently computed over the entire table and returned `ok: True`
with a confidently wrong number.

Fixed by:
- `AnalysisPlan.filters` (Pydantic model in `src/models/schemas.py`) --
  the planner LLM now emits filter conditions alongside columns.
- `src/core/db.py::build_select` compiles them into a parameterized
  `WHERE` clause (`= != > >= < <= LIKE IN BETWEEN`), with filter values
  bound as SQL parameters, never string-interpolated.
- The planner prompt (`src/agents/analysis/prompts.py`) was extended with
  explicit filter examples, including the year-filter pattern
  (`order_date LIKE '2018-%'`, since dates are ISO strings).

Verified empirically: "average profit in the West region" now returns
`33.85` (matches `SELECT AVG(profit) FROM orders WHERE region='West'`
directly), not the old whole-table value of `28.66`.

## 4. Other concrete bugs fixed
- `requirements.txt` was missing `fastmcp` entirely -- a fresh clone
  would fail on the first `import fastmcp`. Added.
- `keyword_route()` checked analysis keywords before the report keyword,
  so "generate a report showing the average profit" routed to `analysis`
  instead of `report`. Report intent is now checked first. Regression
  test: `tests/test_router.py::test_keyword_route_report_wins_over_analysis_keyword`.
- `chart_engine.execute()` and `analysis_engine.load_dataframe()` opened
  SQLite read-write; only `sql_engine` was read-only. All DB access now
  goes through `src/core/db.py`, which is read-only everywhere.
- `mcp_clients.py` had a duplicated import line and hardcoded
  `command="python"` for the stdio transport (now `sys.executable`, so it
  can't silently pick up the wrong interpreter/venv).
- `safety.py` relied on a forbidden-keyword scan to incidentally catch
  stacked statements (`SELECT 1; DROP TABLE orders` was blocked because
  `DROP` is forbidden, not because stacking is rejected by structure).
  Added an explicit check: any semicolon remaining after stripping one
  trailing semicolon is rejected outright.
- `narrate()` accessed `result['answer']['path']` without `.get()` for
  the report branch; a shape mismatch would have raised `KeyError`
  instead of degrading gracefully. Now uses `.get(..., "unknown location")`.

## 5. New shared infrastructure (`src/core/`)
- `db.py` -- the only module that opens a SQLite connection anywhere in
  the codebase.
- `retry.py` -- the one self-correcting retry loop, previously
  copy-pasted three times across SQL/Viz/Analysis.
- `llm_json.py` -- the one "strip fences, parse JSON, raise a clear
  error" helper, previously copy-pasted in Viz/Analysis and reimplemented
  again (differently) in the router.

## 6. New validation layer (`src/models/schemas.py`)
`AnalysisPlan`, `ChartSpec`, `RoutingDecision`, `Filter` -- replace the
hand-rolled `if "x" not in plan: raise ValueError(...)` checks that were
scattered through the engines.

## 7. Tests
- `tests/` now contains only real `pytest` tests (51, all offline, zero
  API calls, run in ~1s): SQL safety guard, `build_select`/filters,
  Pydantic model validation, the retry helper, JSON parsing, router
  (including the ordering-bug regression test), and narrate's
  no-LLM-needed paths.
- `test_llm.py` and `test_router.py` (the old manual live-API scripts)
  moved to `scripts/manual_check/` and are explicitly documented as not
  part of the automated suite -- they still work, they're just not
  pretending to be CI-safe unit tests anymore.

## 8. `docs/architecture.md`
Rewritten to (a) resolve the contradiction between "only the SQL Agent
touches the database" and the actual three-agents-touch-the-database
behavior, by documenting the real, deliberate design (`src/core/db.py` as
the single chokepoint), and (b) explicitly document the conversation-
history decision discussed and agreed on.

## What to do with your existing data/.env
Not touched by any of this -- copy your existing `.env` (with your real
keys, rotated after the earlier leak) and `data/superstore.csv` into this
structure, then re-run `python -m src.ingest` to regenerate
`data/superstore.db` with the sanity-checked ingestion.
