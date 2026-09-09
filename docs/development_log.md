# Development Log

**Project:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Project Objective

Develop a conversational system capable of answering natural language questions over structured datasets using a modular multi-agent architecture based on the Model Context Protocol (MCP).

---

# Milestones 1-10 — System Implementation

Core system built: database ingestion, provider-independent LLM interface, the four-agent architecture (Data Query, Analysis, Visualization, Report) as MCP servers, LangGraph orchestration, and the interactive REPL. See earlier log entries for full detail per milestone.

---

# Milestone 11 — Architecture Cleanup & Correctness Fixes

Centralized all SQLite access in `src/core/db.py`; extracted shared self-correction (`src/core/retry.py`) and JSON-parsing (`src/core/llm_json.py`) helpers; introduced Pydantic validation (`src/models/schemas.py`). Fixed a real correctness bug: the Analysis Agent could only ever `SELECT` whole columns with no `WHERE` clause, silently computing over the entire table for any filtered question. Fixed a router keyword-ordering bug. Removed three stale test files. Test suite: 51 tests.

---

# Milestone 12 — First Evaluation Round (Groq)

55-question benchmark (30 Data Query, 15 Analysis, 10 Visualization) against a minimal baseline, on Groq `llama-3.3-70b`. Found and fixed a real bug: `compute_regression` selected its prediction target by column-list position, silently swapping the target and producing a low-r2 wrong answer. Fixed with an explicit `target` field. Results: architecture value +66.7pp (Data Query), +80.0pp (Analysis), +20.0pp (Visualization); routing accuracy 90.9%. Test suite: 78 tests.

---

# Milestone 13 — Evaluation Consolidation, New Baseline, Bug Fixes, Multi-Provider Final Run

Consolidated 7 evaluation scripts to 3 (`correctness_benchmark.py`, `pipeline_benchmark.py`, `report_agent_benchmark.py`), removing a real redundancy (routing accuracy and pipeline latency were independently re-asking the same 55 questions). Added a second, stronger baseline: a monolithic agent with access to all three real capabilities, deciding for itself which to use, built to isolate "does decomposition into separate agents help" as distinct from "does having tools help at all." Found and corrected a methodological flaw in its own construction: the first version used a hand-written 206-word prompt summary vs. the specialized agents' real combined ~845 words, which would have confounded "architecture" with "less detailed prompting." Fixed by importing the real prompts verbatim.

Found and fixed two more production bugs: a token-limit crash in narration/report generation from large row lists dumped directly into LLM prompts (fixed with a shared `src/core/summarize.py`), and a NaN-handling gap in the scikit-learn-based statistics functions.

Ran the complete evaluation across three providers (Groq, Ollama, Anthropic), documenting real infrastructure findings along the way (Ollama's local model genuinely misrouting unambiguous questions; WSL memory exhaustion under sustained local inference). Anthropic (`claude-haiku-4.5`) was the only provider on which all four evaluation dimensions completed cleanly on one consistent model, and was used as the primary dataset. Added benchmark resumability (`--categories`/`--side`/`--sessions`) and per-pass warm-up calls after repeatedly losing progress to rate limits and infrastructure interruptions. Test suite: 103 tests.

Full results and a question-by-question failure analysis in `results_and_failure_analysis.md`, including two findings that changed how the results should be read: a limitation in the evaluation's own baseline scorer (see Milestone 14), and a chart-time-granularity ambiguity in the question set that fully explained an otherwise-confusing result.

---

# Milestone 14 — Two Real Fixes Found by the Failure Analysis, Applied and Verified

The Milestone 13 failure analysis surfaced two issues worth fixing rather than just documenting. Both were fixed, covered by unit and integration tests against the real database, and the affected part of the evaluation was re-run to confirm the fix directly. Full before/after evidence is in `results_and_failure_analysis.md` §3.2 and §3.5; the summary:

**Fix 1 — `compute_ttest` now compares two groups, not two arbitrary columns.** The old version ran an independent t-test between two numeric *columns* (e.g. discount vs. profit), which is not a valid two-group hypothesis test; a generated report had described its result as "a negative correlation." `AnalysisPlan` gained `group_column` and `group_values` (exactly two, Pydantic-validated), `compute_ttest` now splits by the named categorical column, the benchmark question and its ground truth were rewritten to a genuine group comparison, and Report Agent Session 5 was regenerated. Session 5's accuracy and no-fabrication ratings moved from 2/5 to 5/5.

**Fix 2 — baseline scoring no longer auto-rejects correlation/covariance/t-test.** The scorer had marked those `incorrect` automatically on the assumption a bare SQL model could not express them; in fact the baseline had derived the correct Pearson correlation in raw SQL and was penalised purely by scorer design. `check_baseline_analysis` now checks the actual returned metric. Regression, PCA, and K-Means stay auto-rejected (genuinely infeasible in one non-procedural `SELECT`). Baseline Analysis correctness moved from 20.0% to 40.0% with no change to the baseline's behavior.

Post-fix Anthropic results:

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 40.0% | 80.0% | +60.0pp | +20.0pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Report Agent mean ratings rose from 3.4/5 to 4.0/5 (accuracy and no-fabrication), driven entirely by Session 5. Test suite: 116 tests.

**Not re-run**: Groq and Ollama's correctness data predate both fixes and are not directly comparable to the corrected Anthropic figures. The cross-provider *pattern* (architecture stable, baseline variable) still holds, but a full three-provider re-run was not repeated given the cost already invested; this is stated as a limitation, not implied to be current.

---

# Phase 2 Completed

The empirical evaluation is complete, including two real fixes found by
the evaluation's own failure analysis and independently verified rather
than just documented as limitations. Full results in
`results_and_failure_analysis.md`.
