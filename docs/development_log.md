# Development Log

**Project:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Project Objective

Develop a conversational system capable of answering natural language questions over structured datasets using a modular multi-agent architecture based on the Model Context Protocol (MCP).

---

# Milestones 1-10 — System Implementation

Core system built: database ingestion, provider-independent LLM interface, the four-agent architecture (SQL, Analysis, Visualization, Report) as MCP servers, LangGraph orchestration, and the interactive REPL. See earlier log entries for full detail per milestone.

---

# Milestone 11 — Architecture Cleanup & Correctness Fixes

Centralized all SQLite access in `src/core/db.py`; extracted shared self-correction (`src/core/retry.py`) and JSON-parsing (`src/core/llm_json.py`) helpers; introduced Pydantic validation (`src/models/schemas.py`). Fixed a real correctness bug: the Analysis Agent could only ever `SELECT` whole columns with no `WHERE` clause, silently computing over the entire table for any filtered question. Fixed a router keyword-ordering bug. Removed three stale test files. Test suite: 51 tests.

---

# Milestone 12 — First Evaluation Round (Groq)

55-question benchmark (30 SQL, 15 Analysis, 10 Visualization) against a minimal baseline, on Groq `llama-3.3-70b`. Found and fixed a real bug: `compute_regression` selected its prediction target by column-list position, silently swapping the target and producing a low-r2 wrong answer. Fixed with an explicit `target` field. Results: architecture value +66.7pp (SQL), +80.0pp (Analysis), +20.0pp (Visualization); routing accuracy 90.9%. Test suite: 78 tests.

---

# Milestone 13 — Evaluation Consolidation, New Baseline, Bug Fixes, Multi-Provider Final Run

Consolidated 7 evaluation scripts to 3 (`correctness_benchmark.py`, `pipeline_benchmark.py`, `report_agent_benchmark.py`), removing a real redundancy (routing accuracy and pipeline latency were independently re-asking the same 55 questions). Added a second, stronger baseline: a monolithic agent with access to all three real capabilities, deciding for itself which to use, built to isolate "does decomposition into separate agents help" as distinct from "does having tools help at all." Found and corrected a methodological flaw in its own construction: the first version used a hand-written 206-word prompt summary vs. the specialized agents' real combined ~845 words, which would have confounded "architecture" with "less detailed prompting." Fixed by importing the real prompts verbatim.

Found and fixed two more production bugs: a token-limit crash in narration/report generation from large row lists dumped directly into LLM prompts (fixed with a shared `src/core/summarize.py`), and a NaN-handling gap in the scikit-learn-based statistics functions.

Ran the complete evaluation across three providers (Groq, Ollama, Anthropic), documenting real infrastructure findings along the way (Ollama's local model genuinely misrouting unambiguous questions; WSL memory exhaustion under sustained local inference). Anthropic (`claude-haiku-4.5`) was the only provider on which all four evaluation dimensions completed cleanly on one consistent model, and was used as the primary dataset. Added benchmark resumability (`--categories`/`--side`/`--sessions`) and per-pass warm-up calls after repeatedly losing progress to rate limits and infrastructure interruptions. Test suite: 103 tests.

Full results and a question-by-question failure analysis in `results_and_failure_analysis.md`, including two findings that changed how the results should be read: a limitation in the evaluation's own baseline scorer (see Milestone 14), and a chart-time-granularity ambiguity in the question set that fully explained an otherwise-confusing result.

---

# Milestone 14 — Two Real Fixes Found by the Failure Analysis, Applied and Verified

The evaluation's own failure analysis (Milestone 13) surfaced two issues worth fixing properly rather than just documenting as limitations, given tokens/time were available. Both were fixed, tested at the unit and integration level against the real database, and the affected part of the evaluation was re-run to directly confirm the fix rather than assume it worked.

## Fix 1: `compute_ttest` now compares two groups, not two arbitrary columns

Previous behavior: an independent t-test between two numeric *columns*
directly (e.g. discount vs. profit), not a valid two-group hypothesis
test, since the two "samples" were different variables on different
scales. This was already a documented limitation, and the Milestone 13
Report Agent review had directly demonstrated its real consequence: a
generated report described this test's result as indicating "a negative
correlation," which a t-test does not measure.

Fix: `AnalysisPlan` gained `group_column` and `group_values` fields
(exactly two group values required, Pydantic-validated); `compute_ttest`
now splits the data by the named categorical column and compares the
named variable across the two named groups. The benchmark question
itself was rewritten from the old ambiguous "difference between discount
and profit values" phrasing to a genuine group-comparison question ("is
there a significant difference in profit between the Consumer and
Corporate segments?"), and its ground truth regenerated. The Report
Agent benchmark's Session 5, which had used the old stale phrasing, was
updated to match.

Verified: unit tests (real group comparison, error handling for missing
group data/columns); an integration test through the real Analysis
Agent, matching independently-computed ground truth exactly
(t=-0.856, p=0.392); and, most concretely, the re-generated Report Agent
Session 5 now states the correct conclusion ("there is not a
statistically significant difference... p-value of 0.392 is well above
0.05") in place of the previous misleading claim — the accuracy and
no-fabrication ratings for that session moved from 2/5 to 5/5 as a
direct, measured result.

## Fix 2: baseline scoring no longer auto-rejects correlation/covariance/t-test

Previous behavior: the baseline scorer assumed a bare SQL model could
only possibly succeed at scalar statistics (mean, count, etc.);
correlation, covariance, and t-test were marked incorrect automatically,
regardless of the actual answer. This was found to be a real limitation
of the evaluation itself, not the baseline: Claude's baseline had
manually derived the correct closed-form Pearson correlation formula in
raw SQL and matched the real system's value almost exactly, but was
scored `incorrect` purely by this design.

Fix: `check_baseline_analysis` now genuinely checks the key metric for
correlation, covariance, and t-test against the baseline's actual
returned values. Regression, PCA, and K-Means remain auto-rejected —
correctly: those require iterative optimization or matrix decomposition
a single, non-procedural SQL `SELECT` cannot express, a real structural
limit rather than an unverified assumption.

Verified: unit tests covering correct and incorrect correlation/
covariance/ttest cases, plus confirmation that regression/PCA/K-Means
remain correctly rejected; and a real re-run, which moved baseline
Analysis correctness from 20.0% to 40.0% with zero change to the
baseline's actual behavior. Interestingly, the re-run also surfaced a
genuinely new, honest baseline behavior on the t-test question
specifically: it computed a sophisticated per-group descriptive
breakdown (mean, count, min, max, and a manually-derived standard
deviation via a correlated subquery) but never computed the actual
t-statistic, correctly scored incorrect, since the key metric genuinely
wasn't there. A real demonstration that the fixed scorer rewards genuine
correct answers without becoming lenient.

## Updated results (Anthropic, post-fix)

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 40.0% | 80.0% | +60.0pp | +20.0pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Report Agent mean ratings rose from 3.4/5 to 4.0/5 (accuracy and
no-fabrication), driven entirely by the Session 5 improvement above;
fluency and completeness were already 5.0/5 and unaffected.

Test suite: 116 tests.

**Not re-run**: Groq and Ollama's correctness data predate both fixes and
are not directly comparable to the corrected Anthropic figures, the
cross-provider *pattern* (architecture stable, baseline variable) still
holds, but a full three-provider re-run was not repeated given the cost
already invested, and this is stated explicitly as a limitation rather
than implied to be current.

---

# Phase 2 Completed

The empirical evaluation is complete, including two real fixes found by
the evaluation's own failure analysis and independently verified rather
than just documented as limitations. Full results in
`results_and_failure_analysis.md`.
