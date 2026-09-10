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

**Not re-run**: Groq and Ollama's Analysis-category data predates both fixes and is excluded from §5 as non-comparable (Data Query and Visualization are untouched by the fixes and are kept). A full three-provider re-run was not repeated given the cost already invested; this is stated as a limitation. See Milestone 16 for the re-run attempt and `results_and_failure_analysis.md` §5 for the full cross-provider tables.

---

# Milestone 15 — Adversarial Report-Agent session

Added a sixth Report-Agent session. The other five use normal questions; this one uses six questions that can't be answered from the data at all (a column that isn't there, a customer that doesn't exist, a metric we don't have, a country not in the data, a "why" question, a chart of a non-existent column). The point is to see if the Report Agent admits it or makes something up. Run on Anthropic Haiku 4.5.

What happened (details in `results_and_failure_analysis.md` §4.2): the Report Agent mostly just repeats what it's given. It doesn't invent age or marketing numbers and marks those turns as failed. But it put the impossible "employee salary vs profit" chart under "Successful Queries" as a plain sales-vs-profit chart and added a "positive correlation" claim that no agent computed (no-fabrication 2/5, failure-transparency 3/5). The bigger problem is upstream: the Data Query and Analysis planners quietly swap `sales` in for the missing column instead of saying it's missing. The retry loop ran for the first time (two turns hit `attempts: 3`) but couldn't fix anything, because a missing column isn't a syntax error you can retry. Tests unchanged (this benchmark needs a live LLM).

---

# Milestone 16 — Cross-provider tables, and a re-run attempt

Put all the cross-provider results into one set of tables in `results_and_failure_analysis.md` §5, one row per thing measured and one column per provider (Ollama, Groq, Anthropic). Cells we don't have are left blank, not guessed. §5.1 is a small table listing what was and wasn't run on each provider. For Groq and Ollama I kept only the numbers that were measured the same way as Anthropic (Data Query and Visualization correctness, retry rate); their Analysis numbers and Groq's old routing number are pre-fix, so they're left out.

Tried to re-run Groq and Ollama to fill the gaps. Both failed (see §5.7):

- **Groq**: the model used for the first Groq run, `llama-3.3-70b-versatile`, was removed by Groq and now returns `model_not_found`. There's no Llama model on Groq anymore. `openai/gpt-oss-120b` works, but the free tier only allows 8,000 tokens/minute, and the full run needs far more than that (the monolithic agent's prompt alone is big), so it stalls. The registry now points `groq` at `openai/gpt-oss-120b` with a comment, so `TFG_MODEL=groq` still runs.
- **Ollama**: `llama3.1:8b` still works, but each question takes 25–210 s, so the full run is several hours on a machine that already ran out of memory once. Didn't finish.

So the cross-provider comparison is solid for Data Query and Visualization correctness (all three providers, same conditions) and for the "architecture beats baseline" pattern (all three). It's Anthropic-only for decomposition value, latency, per-category routing, per-difficulty, and the Report Agent.

---

# Milestone 17 — Spanish and Catalan

Ran the evaluation again with the 55 questions and the 6 Report-Agent sessions translated into Spanish and Catalan, to check if the language of the question matters. Only on Anthropic Haiku 4.5; Groq and Ollama weren't re-run for the same reasons as Milestone 16, so those columns are blank.

The language support is built in, not bolted on: `question` in the dataset files is now a `{en, es, ca}` dict (still one file, one ground truth, since the SQL and expected answers don't depend on language); every benchmark takes `--language {en,es,ca}`; output goes to `results/eval/<model>/<language>/` (so a different model won't overwrite). The English results moved into `results/eval/anthropic/en/` as a git rename - `build_summary("en")` still produces the same `summary.csv`. Value names like "West" and "Technology" stay in English in all languages; the system prompts stay in English too.

Findings (details in §7):

- The system does about the same in all three languages. Real-system correctness stays 90–100%; routing 90.9 / 92.7 / 90.9%; latency close. Every wrong answer from the real agents is one of the two ambiguities already found in English (§3.1 order counting, §3.3 chart granularity) - none is the model misunderstanding the language. The baseline fails on the same questions in every language.
- The retry loop recovered for the first time in the whole project, in the Catalan Analysis run (bad JSON, retried, second try correct).
- The one real gap: the Report Agent always writes its report in English, even when the conversation was in Spanish or Catalan (the narration and number formatting do follow the language). A one-line prompt change would fix it.
- Session 6 (adversarial) went a bit better in es/ca: the English viz agent invented a fake "employee salary" axis and the English report claimed a correlation, while es/ca just said "Sales vs Profit". Luck, but worth noting.

Tests: 116 (offline suite unchanged; the language benchmarks need a live LLM).

---

# Phase 2 Completed

The empirical evaluation is complete, including two real fixes found by
the evaluation's own failure analysis and independently verified rather
than just documented as limitations. Full results in
`results_and_failure_analysis.md`.
