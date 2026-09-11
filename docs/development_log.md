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

Moved all SQLite access into one place (`src/core/db.py`); pulled the repeated self-correction retry code (`src/core/retry.py`) and JSON-parsing code (`src/core/llm_json.py`) into shared helpers; added Pydantic validation (`src/models/schemas.py`). Fixed a real bug: the Analysis Agent could only `SELECT` whole columns with no `WHERE` clause, so it silently ran over the whole table even when the question asked for a filter. Fixed a router bug about keyword order. Removed three old test files that no longer matched the code. Test suite: 51 tests.

---

# Milestone 12 — First Evaluation Round (Groq)

Ran the 55-question benchmark (30 Data Query, 15 Analysis, 10 Visualization) against a minimal baseline, on Groq `llama-3.3-70b`. Found and fixed a real bug: `compute_regression` picked its prediction target by its position in the column list, so it could silently pick the wrong column and give a low-r2 wrong answer. Fixed by adding an explicit `target` field. Results: architecture value +66.7pp (Data Query), +80.0pp (Analysis), +20.0pp (Visualization); routing accuracy 90.9%. Test suite: 78 tests.

---

# Milestone 13 — Evaluation Consolidation, New Baseline, Bug Fixes, Multi-Provider Final Run

Merged 7 evaluation scripts down to 3 (`correctness_benchmark.py`, `pipeline_benchmark.py`, `report_agent_benchmark.py`) - routing accuracy and pipeline latency were separately re-asking the same 55 questions, which was pointless. Added a second, stronger baseline: a monolithic agent that has all three real capabilities and picks for itself which to use. This lets us separate two different questions: "does splitting the work into separate agents help" vs. "does just having the tools help at all." While building it, found a mistake in how I'd set it up: the first version used a short hand-written 206-word prompt, while the real specialized agents' combined prompts are about 845 words - that would have mixed up "the architecture is better" with "the prompt has less detail." Fixed by copying in the real prompts as they are.

Found and fixed two more real bugs: a token-limit crash in narration/report generation, caused by dumping large row lists straight into the LLM prompt (fixed with a shared `src/core/summarize.py`), and a gap in the scikit-learn-based statistics functions that didn't handle NaN values.

Ran the full evaluation on three providers (Groq, Ollama, Anthropic), and along the way found some real infrastructure problems (Ollama's local model really did misroute questions that should have been obvious; WSL ran out of memory during long local runs). Anthropic (`claude-haiku-4.5`) was the only provider where all four parts of the evaluation finished cleanly on one model, so it became the main dataset. Added the ability to resume a benchmark partway (`--categories`/`--side`/`--sessions`) and a warm-up call before each pass, after losing progress more than once to rate limits and other interruptions. Test suite: 103 tests.

Full results and a question-by-question look at what went wrong are in `results_and_failure_analysis.md`, including two findings that changed how to read the results: a problem in the evaluation's own baseline scorer (see Milestone 14), and a chart-time-granularity question that fully explained a result that looked confusing at first.

---

# Milestone 14 — Two Real Fixes Found by the Failure Analysis, Applied and Verified

Looking closely at the Milestone 13 results turned up two things worth actually fixing, not just writing down. Both were fixed, covered by unit and integration tests against the real database, and the affected part of the evaluation was re-run to check the fix worked. Full before/after details are in `results_and_failure_analysis.md` §3.2 and §3.5; short version:

**Fix 1 - `compute_ttest` now compares two groups, not two random columns.** The old version ran a t-test between two numeric *columns* directly (e.g. discount vs. profit), which isn't what a t-test is for - a real t-test compares one variable across two *groups*. A generated report had even described the result as "a negative correlation," which is wrong. `AnalysisPlan` now has `group_column` and `group_values` fields (exactly two values, checked by Pydantic), `compute_ttest` splits the data by that column, the benchmark question and its ground truth were rewritten to a real group comparison, and Report Agent Session 5 was regenerated. Session 5's accuracy and no-fabrication ratings went from 2/5 to 5/5.

**Fix 2 - baseline scoring no longer auto-rejects correlation/covariance/t-test.** The scorer used to mark those `incorrect` automatically, assuming a plain SQL model couldn't do them - but the baseline had actually worked out the correct Pearson correlation in raw SQL and was being marked wrong just because of how the scorer worked. `check_baseline_analysis` now checks the real number it returned. Regression, PCA, and K-Means still get auto-rejected, correctly - those really can't be done in one plain `SELECT`. Baseline Analysis correctness went from 20.0% to 40.0% with no change to what the baseline actually does.

Post-fix results (Model: Anthropic Claude Haiku 4.5. Language: English.):

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 40.0% | 80.0% | +60.0pp | +20.0pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Report Agent mean ratings rose from 3.4/5 to 4.0/5 (accuracy and no-fabrication), driven entirely by Session 5. Test suite: 116 tests.

**Not re-run**: Groq and Ollama were not re-run after the fixes. Their earlier runs predate the final system, so their numbers are not reported (see Milestone 16 and §5).

---

# Milestone 15 — Adversarial Report-Agent session

Added a sixth Report-Agent session. The other five use normal questions; this one uses six questions that can't be answered from the data at all (a column that isn't there, a customer that doesn't exist, a metric we don't have, a country not in the data, a "why" question, a chart of a non-existent column). The point is to see if the Report Agent admits it or makes something up. Run on Anthropic Haiku 4.5.

What happened (details in `results_and_failure_analysis.md` §4.2): the Report Agent mostly just repeats what it's given. It doesn't invent age or marketing numbers and marks those turns as failed. But it put the impossible "employee salary vs profit" chart under "Successful Queries" as a plain sales-vs-profit chart and added a "positive correlation" claim that no agent computed (no-fabrication 2/5, failure-transparency 3/5). The bigger problem is upstream: the Data Query and Analysis planners quietly swap `sales` in for the missing column instead of saying it's missing. The retry loop ran for the first time (two turns hit `attempts: 3`) but couldn't fix anything, because a missing column isn't a syntax error you can retry. Tests unchanged (this benchmark needs a live LLM).

---

# Milestone 16 — Decided not to report Groq/Ollama numbers yet

Looked at putting the early Groq and Ollama results into `results_and_failure_analysis.md` §5, then decided against reporting any of their numbers until there is a clean run to back them up:

- The Groq and Ollama runs are from early in the project and predate the architecture restructure and both fixes (§3.2, §3.5), so they don't match the final system.
- The Groq first run is still in git history (commit `354902e`), but the Ollama run was overwritten before it was committed, so there is no per-question detail for it - only the aggregate numbers, in an old version of this log.
- Tried to re-run Groq on the same model: `llama-3.3-70b-versatile` was removed by Groq and returns `model_not_found`. There's no Llama model on Groq anymore. `openai/gpt-oss-120b` works, but the free tier only allows 8,000 tokens/minute, which isn't enough for a full run. The registry now points `groq` at `openai/gpt-oss-120b` with a comment so `TFG_MODEL=groq` still runs.
- Ollama can be re-run (tokens are free locally) but it's slow (25-210 s per question) and has hit memory limits before. This re-run is planned.

So §5 now just explains this. All reported results are Anthropic Haiku. The main open item is an Ollama re-run on the final system.

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

# Milestone 18 — Real Ollama re-run (English, Spanish, Catalan), and a plain-language pass

Did the clean Ollama re-run that Milestone 16 said was planned, for all three languages. Written into `results_and_failure_analysis.md` §5.3-5.7 with real numbers.

Main findings:

- The real system stays close to Anthropic on this much smaller local model on English and Spanish (83-100% vs 90-100% correctness), and even beats it on Visualization. Catalan is noticeably weaker (70-93%), but the machine was also least stable during that run (see below), so language and machine fatigue are tangled together and can't be fully separated. The baseline is much weaker on Data Query in every language, because a small model writing plain SQL with no tools makes real mistakes.
- The router is the actual weak point: it sends about 80% of Data Query questions to Analysis, in all three languages. Checked what happened to those questions by hand (same method as §3.4) - unlike Anthropic's routing mix-ups, these produce genuinely wrong answers a user would see and believe, because the Analysis agent's fixed menu can't group-and-rank.
- The same specific SQL mistakes (mixing up "revenue" with "profit", taking the min/max of one row instead of grouping first, missing `LIMIT 1`) show up in all three languages - real weaknesses of the model, not something caused by translation. Catalan added two mistakes not seen in English or Spanish: confusing "Region" with "State", and picking a plain `describe` instead of K-Means for a clustering question.
- The machine slows down the longer it runs: the English `run_all` took about 3 hours, the same Spanish run took 7.5 hours. Checked this directly - the CPU wasn't maxed out, but the machine ran low on RAM and was swapping, on a 15 GB laptop already almost fully used between Windows and the WSL2 VM running Ollama. The Catalan run was the least stable of the three: `dmesg` showed the laptop went to sleep and resumed mid-run, and the Ollama server crashed outright on one question.
- The worst fabrication found anywhere in this project: asked for a "correlation between marketing spend and profit" (a column that doesn't exist), the model silently used a real column instead and reported a confident, precise correlation as fact, in all three languages. Every other run on this same question (Anthropic in all three languages) either errored or refused.
- The same cross-provider pattern seen on Anthropic showed up again on Ollama: the impossible "employee salary vs profit" chart was hallucinated in English but correctly called "sales vs profit" in Spanish, with no invented numbers. Catalan's Visualization agent also avoided the fabrication, but the Report Agent then wrote it up as "employee salary" anyway - so the honesty found lower in the pipeline didn't make it into the final report. Catalan's Report Agent also fabricated a complete, plausible-looking answer for a turn that had actually crashed with a technical error, and mislabeled raw sample rows as computed quartiles/median/outliers in another turn - the worst report-agent fabrications found anywhere in this project.

Also went back through the whole repo - explanatory files and code comments - and rewrote the parts that read too polished or used complex words, so it reads like it was written by a student learning this, not a professional report. Checked the offline test suite after each change; all 116 still pass throughout.

---

# Phase 2 Completed

The evaluation is done, including two real fixes that were found while
looking at the results, applied, and checked - not just written down as
limitations. Full results in `results_and_failure_analysis.md`.
