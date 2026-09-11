# Development Log

**Project:** Multi-Agent Conversational Data Analysis System


**Author:** Eric Amargant Gutiérrez


**Supervisor:** Piotr Przybyła

---

# Project Objective

My goal was to build a conversational system that can answer natural language questions about structured data, using a multi-agent architecture built on the Model Context Protocol (MCP).

---

# Milestones 1-10 — Building the System

I built the core system: loading the data into the database, an LLM interface that works with any provider, the four-agent architecture (Data Query, Analysis, Visualization, Report) as MCP servers, the LangGraph orchestration, and the interactive REPL. See earlier log entries for the full detail of each milestone.

---

# Milestone 11 — Architecture Cleanup and Correctness Fixes

I moved all the SQLite database access into one place (`src/core/db.py`). I also pulled the retry code that was copied three times (`src/core/retry.py`) and the JSON-parsing code (`src/core/llm_json.py`) into shared helper functions, and added Pydantic validation (`src/models/schemas.py`). I fixed a real bug: the Analysis Agent could only `SELECT` whole columns with no `WHERE` clause, so it silently ran over the whole table even when the question asked for a filter. I also fixed a router bug about keyword order, and removed three old test files that no longer matched the code. Test suite: 51 tests.

---

# Milestone 12 — First Evaluation Round (Groq)

I ran the 55-question benchmark (30 Data Query, 15 Analysis, 10 Visualization) against a simple baseline, on Groq `llama-3.3-70b`. I found and fixed a real bug: `compute_regression` picked its prediction target by its position in the column list, so it could silently pick the wrong column and give a wrong answer with a low r². I fixed this by adding an explicit `target` field. Results: architecture value +66.7pp (Data Query), +80.0pp (Analysis), +20.0pp (Visualization); routing accuracy 90.9%. Test suite: 78 tests.

---

# Milestone 13 — Merging the Evaluation, a New Baseline, Bug Fixes, First Full Run

I merged 7 evaluation scripts down to 3 (`correctness_benchmark.py`, `pipeline_benchmark.py`, `report_agent_benchmark.py`), because routing accuracy and pipeline latency were separately asking the same 55 questions again, which was pointless. I added a second, stronger baseline: one agent that has all three real tools and picks by itself which one to use. This lets me separate two different questions: "does splitting the work into separate agents help" and "does just having the tools help at all." While building it, I found a mistake in how I had set it up: the first version used a short prompt I wrote myself (206 words), while the real specialized agents' combined prompts are about 845 words. That would have mixed up "the architecture is better" with "the prompt has less detail." I fixed it by copying in the real prompts exactly as they are.

I found and fixed two more real bugs: a token-limit crash when narrating an answer or writing a report, caused by putting large row lists straight into the LLM prompt (I fixed this with a shared `src/core/summarize.py`), and a gap in the scikit-learn statistics functions, which did not handle missing (NaN) values.

I ran the full evaluation on three providers (Groq, Ollama, Anthropic), and found some real problems along the way (Ollama's local model really did send questions to the wrong agent, even when it should have been obvious; WSL ran out of memory during long local runs). Anthropic (`claude-haiku-4.5`) was the only provider where all four parts of the evaluation finished cleanly on one model, so it became the main dataset. I added the ability to resume a benchmark partway through (`--categories`/`--side`/`--sessions`) and a warm-up call before each run, after losing progress more than once to rate limits and other interruptions. Test suite: 103 tests.

The full results, and a question-by-question look at what went wrong, are in `results_and_failure_analysis.md`. This includes two findings that changed how to read the results: a problem in my own baseline scorer (see Milestone 14), and a chart-grouping question that fully explained a result that looked confusing at first.

---

# Milestone 14 — Two Real Fixes Found by the Failure Analysis, Applied and Checked

When I looked closely at the Milestone 13 results, I found two things worth actually fixing, not just writing down. I fixed both, wrote unit and integration tests against the real database for them, and re-ran the affected part of the evaluation to check the fix worked. The full before-and-after is in `results_and_failure_analysis.md` §3.2 and §3.5. Short version:

**Fix 1 - `compute_ttest` now compares two groups, not two random columns.** The old version ran a t-test between two numeric *columns* directly (e.g. discount vs. profit), which is not what a t-test is for - a real t-test compares one variable across two *groups*. A generated report had even described the result as "a negative correlation," which is wrong. `AnalysisPlan` now has `group_column` and `group_values` fields (exactly two values, checked by Pydantic), `compute_ttest` splits the data by that column, and I rewrote the benchmark question and its ground truth to be a real group comparison. I also regenerated Report Agent Session 5. Session 5's accuracy and no-fabrication ratings went from 2/5 to 5/5.

**Fix 2 - baseline scoring no longer marks correlation, covariance, and t-test wrong automatically.** The scorer used to mark those `incorrect` automatically, assuming a plain SQL model could not do them. But the baseline had actually worked out the correct Pearson correlation in raw SQL, and it was only marked wrong because of how the scorer worked. `check_baseline_analysis` now checks the real number it returned. Regression, PCA, and K-Means are still marked wrong automatically, and correctly so - those really cannot be done in one plain `SELECT`. Baseline Analysis correctness went from 20.0% to 40.0%, with no change to what the baseline actually does.

Post-fix results (Model: Anthropic Claude Haiku 4.5. Language: English.):

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% | 76.7% | 90.0% | +16.7pp | +3.3pp |
| Analysis | 100% | 40.0% | 80.0% | +60.0pp | +20.0pp |
| Visualization | 90.0% | 50.0% | 100% | +40.0pp | -10.0pp |

Report Agent mean ratings rose from 3.4/5 to 4.0/5 (accuracy and no-fabrication), and this was entirely because of Session 5. Test suite: 116 tests.

**Not re-run**: I did not re-run Groq and Ollama after these fixes. Their earlier runs happened before the final system existed, so I don't report their numbers (see Milestone 16 and §5).

---

# Milestone 15 — A Report-Agent Session with Impossible Questions

I added a sixth Report-Agent session. The other five use normal questions; this one uses six questions that cannot be answered from the data at all (a column that does not exist, a customer that does not exist, a metric I don't have, a country not in the data, a "why" question, and a chart of a column that does not exist). The point is to see if the Report Agent admits this or makes something up. I ran it on Anthropic Haiku 4.5.

What happened (details in `results_and_failure_analysis.md` §4.2): the Report Agent mostly just repeats what it is given. It does not invent age or marketing numbers, and it marks those turns as failed. But it put the impossible "employee salary vs profit" chart under "Successful Queries" as a plain sales-vs-profit chart, and it added a "positive correlation" claim that no agent had actually computed (no-fabrication 2/5, failure-transparency 3/5). The bigger problem happens earlier: the Data Query and Analysis planners quietly use `sales` instead of saying the column is missing. The retry loop ran for the first time here (two turns hit `attempts: 3`), but it could not fix anything, because a missing column is not a syntax error that a retry can fix. Tests unchanged (this benchmark needs a live LLM).

---

# Milestone 16 — Deciding Not to Report Groq/Ollama Numbers Yet

I thought about putting the early Groq and Ollama results into `results_and_failure_analysis.md` §5, then decided not to report any of their numbers until I had a clean run to back them up:

- The Groq and Ollama runs are from early in the project, before I restructured the architecture and made both fixes (§3.2, §3.5), so they don't match the final system.
- The first Groq run is still in git history (commit `354902e`), but the Ollama run was overwritten before I committed it, so there is no per-question detail for it - only the total numbers, in an old version of this log.
- I tried to re-run Groq on the same model: `llama-3.3-70b-versatile` was removed by Groq and now returns `model_not_found`. There is no Llama model on Groq anymore. `openai/gpt-oss-120b` works, but the free tier only allows 8,000 tokens per minute, which is not enough for a full run. The registry now points `groq` at `openai/gpt-oss-120b`, with a comment explaining why, so `TFG_MODEL=groq` still works.
- I can re-run Ollama (tokens are free on my own computer), but it is slow (25-210 seconds per question) and has hit memory limits before. I am planning this re-run.

So §5 just explains this for now. All the results I report are from Anthropic Haiku. The main thing still open is an Ollama re-run on the final system.

---

# Milestone 17 — Spanish and Catalan

I ran the evaluation again with the 55 questions and the 6 Report-Agent sessions translated into Spanish and Catalan, to check if the language of the question matters. I only did this on Anthropic Haiku 4.5; I did not re-run Groq and Ollama, for the same reasons as Milestone 16, so those columns are blank.

The language support is a real part of the design, not something added on top: `question` in the dataset files is now a `{en, es, ca}` dictionary (still one file, one ground truth, since the SQL and the expected answers do not change with language). Every benchmark takes a `--language {en,es,ca}` flag, and the output goes to `results/eval/<model>/<language>/` (so a different model does not overwrite it). I moved the English results into `results/eval/anthropic/en/` as a git rename - `build_summary("en")` still makes the same `summary.csv`. Value names like "West" and "Technology" stay in English in every language, and the system prompts stay in English too.

Findings (details in §7):

- The system works about the same in all three languages. Real-system correctness stays between 90-100%; routing is 90.9 / 92.7 / 90.9%; latency is close. Every wrong answer from the real agents is one of the two unclear cases already found in English (§3.1 order counting, §3.3 chart grouping) - none of them is the model misunderstanding the language. The baseline fails on the same questions in every language.
- The retry loop worked for the first time in the whole project, in the Catalan Analysis run (bad JSON, it tried again, and the second try was correct).
- The one real gap: the Report Agent always writes its report in English, even when the conversation was in Spanish or Catalan (the narration and number format do follow the language). Changing one line in the prompt would fix this.
- Session 6 (the impossible-questions one) went a bit better in Spanish and Catalan: the English Viz Agent invented a fake "employee salary" axis, and the English report claimed a correlation, while Spanish and Catalan just said "Sales vs Profit." This looks like luck, but it is still worth noting.

Tests: 116 (the offline suite did not change; the language benchmarks need a live LLM).

---

# Milestone 18 — Real Ollama Re-run (English, Spanish, Catalan), and a Plain-Language Pass

I did the clean Ollama re-run that Milestone 16 said I was planning, for all three languages. I wrote it into `results_and_failure_analysis.md` §5.3-5.7 with real numbers.

Main findings:

- The real system stays close to Anthropic, even on this much smaller local model, in English and Spanish (83-100% vs 90-100% correctness), and it even does better on Visualization. Catalan is clearly weaker (70-93%), but my machine was also the least stable during that run (see below), so I cannot fully separate a real language effect from a tired machine. The baseline is much weaker on Data Query in every language, because a small model writing plain SQL with no tools makes real mistakes.
- The router is the real weak point: it sends about 80% of Data Query questions to Analysis, in all three languages. I checked what happened to those questions by hand (the same method as §3.4) - unlike Anthropic's routing mistakes, these give a genuinely wrong answer that a user would see and believe, because the Analysis Agent's fixed list of functions cannot group and rank data.
- The same SQL mistakes (mixing up "revenue" with "profit", taking the min/max of one row instead of grouping first, missing `LIMIT 1`) show up in all three languages. These are real weaknesses of the model, not something caused by translation. Catalan added two mistakes not seen in English or Spanish: mixing up "Region" with "State," and picking a plain `describe` instead of K-Means for a clustering question.
- The machine gets slower the longer it runs: the English `run_all` took about 3 hours, but the same Spanish run took 7.5 hours. I checked this directly - the CPU was not fully used, but the machine was low on memory (RAM) and was swapping, on a 15 GB laptop that was already almost full between Windows and the WSL2 virtual machine running Ollama. The Catalan run was the least stable of the three: `dmesg` showed that the laptop went to sleep and woke up again in the middle of the run, and the Ollama server crashed completely on one question.
- The worst made-up answer found anywhere in this project: when asked for a "correlation between marketing spend and profit" (a column that does not exist), the model silently used a real column instead and reported an exact correlation number as if it were fact, in all three languages. Every other run on this same question (Anthropic, in all three languages) either gave an error or refused to answer.
- The same pattern I saw on Anthropic showed up again on Ollama: the impossible "employee salary vs profit" chart was made up in English, but correctly called "sales vs profit" in Spanish, with no invented numbers. Catalan's Visualization Agent also avoided making things up, but the Report Agent then wrote it up as "employee salary" anyway - so being honest earlier in the pipeline did not make it into the final report. Catalan's Report Agent also invented a complete, believable-looking answer for a turn that had actually crashed with a technical error, and in another turn it labeled raw sample rows as computed quartiles, median, and outliers - the worst report-agent fabrications found anywhere in this project.

I also went back through the whole repository - explanation files and code comments - and rewrote the parts that read too polished or used complex words, so it reads like it was written by a student who is learning this, not like a professional report. I checked the offline test suite after each change; all 116 tests kept passing.

---

# Phase 2 Completed

The evaluation is done. This includes two real fixes that I found while
looking at the results, applied, and checked - not just written down as
limitations. Full results are in `results_and_failure_analysis.md`.
