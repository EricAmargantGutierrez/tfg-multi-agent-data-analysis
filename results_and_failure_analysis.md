# Evaluation Results and Failure Analysis

## 1. Methodology recap

The system was tested four ways:

1. **Correctness** - the real specialized agents vs. two baselines, per category (Data Query, Analysis, Visualization), checked against ground truth (computed directly, never by an LLM - see below).
2. **Decomposition value** - the real agents vs. a *monolithic* agent with the exact same tools and prompts (copied in, not paraphrased) but as one agent, not split up. This separates "does splitting into agents help" from "does just having the tools help."
3. **Routing accuracy and end-to-end latency** - measured in one pass through the real orchestrator (router -> agent -> narrator), kept separate from the correctness runs, which force routing so each agent's own ability can be checked alone.
4. **Report Agent quality** - checked by hand, not scored: a session summary has no single right answer, so it's rated on accuracy, completeness, no-fabrication, and fluency. Five normal sessions plus one session with impossible questions, to see if the agent makes something up.

**Only accuracy can be pulled down by a mistake that isn't the Report Agent's own fault.** If an earlier turn got a wrong answer (the agent's mistake, or a routing mistake) and the Report Agent just repeats it unchanged, that counts against **accuracy** - accuracy asks whether what the report says is correct, not just whether it matches what it was given. **No-fabrication** only looks at whether the Report Agent invented something nobody computed (repeating someone else's wrong answer isn't that); **completeness** and **fluency** don't depend on correctness either. So a report can score low on accuracy and high on the other three in the same session.

All comparisons use structured output (rows, statistics results), never the narrated text, since the same correct answer can be worded many ways. The baseline uses a short, generic prompt, not the agents' tuned ones, to show the value of the whole architecture; the monolithic agent uses the *same* tuned prompts, copied in verbatim, to isolate the value of splitting the work up. This was a deliberate choice, checked before any evaluation ran: an earlier draft of the monolithic agent used a short prompt I wrote myself, much shorter than the real agents' combined prompts (1,131 words). Using that shorter version would have made it impossible to tell whether a difference in results was really about the architecture (one agent vs. several) or just about a less detailed prompt, so I replaced it with the real prompts, copied in exactly as they are.

**How scoring works.** Data Query and Visualization answers are scored by comparing the returned rows against the ground-truth rows: order doesn't matter, count does (a duplicate row must appear the same number of times), and numbers are matched with a small tolerance (0.01). Analysis answers are scored by comparing the specific statistic returned (mean, `t_statistic`, regression r², ...) to the ground-truth value, also with a tolerance. The Report Agent is scored subjectively, by hand, since a summary has no single correct answer to check.

**Where the ground truth comes from.** It's produced by a script (`src/eval/ground_truth/`) that runs a hand-written reference SQL query or analysis plan against the real database - no LLM involved, so it's repeatable, but only as correct as those reference queries, which I wrote myself. The evaluation did find and fix a real bug in one of them (the t-test reference, further down), so this is a real dependency, not a formality.

All three providers are called as plain text-completion models: one prompt in, one block of text out, no tool-use/function-calling API, no web search, no retrieval. This is about how the model is called, not whether real computation happens - it does, differently for each agent that touches the database:

- **Data Query**'s output is the SQL query itself, as plain text - the model writes it directly, and that exact text runs.
- **Visualization**'s output is a JSON object that includes a SQL query the model writes itself, same as Data Query - so unlike Analysis, it *does* write its own SQL. It also picks the chart type from a fixed list of 6, similar to how Analysis picks a statistic: the model decides *which*, not how to draw it.
- **Analysis**'s output is a JSON plan naming one of 15 pre-written functions (mean, correlation, regression, PCA, K-Means, ...) and its parameters; separate Python code (not the LLM) runs that function against the real data (§4.5 has more on this). Unlike the other two, it never writes any SQL - the columns and filters it names are turned into a query by other code.

So the model always decides *what* to do, but the actual computation never comes from code it wrote itself, and the only thing that varies between providers is the model's reasoning, not what tools it can reach.

Every LLM call uses `temperature=0` on every provider (`src/llm/factory.py`), keeping answers close to the same each time so re-running the benchmark gives similar results - not perfectly identical (a live API can still vary a little), but with most of the randomness removed.

The benchmark has 55 questions: 30 Data Query, 15 Analysis, 10 Visualization, split into easy/medium/hard. With so few per category, one flipped answer moves the percentage a lot: 3.3pp per question in Data Query, 6.7pp in Analysis, 10pp in Visualization. Keep this in mind throughout - a 10pp gap in Visualization can be one question.

This document explains each model fully, one at a time - Anthropic first (§2, the main reference model, in English and then Spanish/Catalan), then the two local models (§3: why Groq isn't one of them, then Llama, then Salamandra) - and only compares them to each other at the end of §3 and in the conclusions (§4).

**The three models, as models** (a quick side-by-side before any results - not as measured in this evaluation, that's the rest of this document):

| | Anthropic Claude Haiku 4.5 | Meta Llama 3.1 8B | BSC-LT Salamandra 7B Instruct |
|---|---|---|---|
| Parameters | Not published | 8B | 7.77B |
| Context window | 200,000 tokens | 128,000 tokens | 8,192 tokens |
| Released | Oct 2025 | Jul 2024 | 2024 |
| Hosting | Hosted API, paid | Local, free | Local, free |
| Languages | No fixed published list - broadly multilingual from scale and training data, nothing specific documented for Catalan | 8 languages officially fine-tuned and safety-tested (not including Catalan), trained on more than that | 35 European languages, with Spanish/Catalan/Galician/Basque oversampled 2x |
| License / cost | Proprietary, $1 / $5 per million tokens (in/out) | Free (Llama license) | Free (Apache 2.0) |

Why each one is in this evaluation: **Anthropic** is the upper-bound reference - a strong, fast, hosted model, to see what the architecture looks like on something clearly capable. **Llama 3.1 8B** is the general-purpose local baseline - small, free, and not specifically tuned for one of this project's two non-English languages. **Salamandra 7B** is the targeted counterpoint - same size as Llama, but built for exactly the languages Llama wasn't specially tuned for. §3.1 and §3.4 explain how Salamandra specifically was chosen, and what came of it.

---

## 2. Anthropic Claude Haiku 4.5

This was the first model tested, and English was run first - before Spanish and Catalan questions existed, and before two real bugs (§2.2) were found and fixed. But the three sections below treat all three languages together throughout, as one table each, not English as the main event with the other two tacked on at the end.

### 2.1 Correctness, routing, latency, and retries

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish (ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" = monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 93.3% | 76.7% | 90.0% | 93.3% | 73.3% | 86.7% | 100% | 76.7% | 93.3% |
| Analysis | 100% | 40.0% | 80.0% | 100% | 40.0% | 93.3% | 100% | 40.0% | 86.7% |
| Visualization | 90.0% | 50.0% | 100% | 90.0% | 60.0% | 90.0% | 90.0% | 60.0% | 90.0% |

("pp" means percentage points, e.g. 93.3% minus 76.7% is 16.7pp, not "16.7%" - used throughout wherever two percentages are compared directly. The Analysis figures are the numbers *after* two real bugs were found and fixed during this evaluation - before them, English's baseline was 20.0% and monolithic was 86.7%. Both fixes are explained in full in §2.2, with before/after evidence.)

The real system stays in a tight 90-100% band in every language and every category - the small differences (Data Query reaching 100% in Catalan, Visualization sitting at 90% everywhere) trace to two specific known ambiguities in the question set (§2.2), not to the model handling one language worse than another. The baseline is the clearest illustration of *why* the architecture matters, and it's consistent across languages: on Data Query, where a plain SQL query really can answer most questions, it stays reasonably competitive (73-77%); on Analysis, where real statistics are needed, it collapses to 40% in every single language, since a bare SQL model cannot compute a regression or a PCA no matter what language it's asked in (§2.2 explains exactly what it can and can't do). That's also why the gap between the real system and the baseline is small for Data Query but large for Analysis in every language - the baseline was never going to be close on Analysis, language aside.

Whether splitting the work into separate agents helps *on top of* just having the tools (the monolithic agent has the same tools, just not split up) tells a different story by category: modest and mixed for Data Query and Visualization (even slightly negative for Visualization in English, entirely from one ambiguous chart question, §2.2), but consistently positive for Analysis in all three languages (+20.0pp English, +6.7pp Spanish, +13.3pp Catalan) - splitting the "which statistic do I compute" decision out into its own agent adds real value on its own, not just "having the tools" value, and that holds regardless of language.

**Routing accuracy:**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 90.9% | 92.7% | 90.9% |
| Data Query | 100% | 100% | 96.7% |
| Analysis | 66.7% | 73.3% | 73.3% |
| Visualization | 100% | 100% | 100% |

Routing works about the same everywhere. The one weak spot (Analysis, 66.7-73.3%) is the same pattern in every language: an average/median question sent to Data Query instead of Analysis - 5 questions in English ("average discount," "median profit," "average profit West region," "average sales East/Furniture," "median sales South region"), 4 in Spanish, 5 in Catalan (Catalan's extra one, "Quin client va fer més comandes?" - "which customer made the most orders" - also went to Analysis). **These are not real errors.** A mean or median is just `AVG(...)` or a percentile query, answerable by either agent, and checking every one of these by hand against the ground truth - 0.156 (avg discount), 8.67 (median profit), $33.85 (avg profit West), $346.57 (avg sales East/Furniture), $54.66 (median sales South), and the equivalent Spanish/Catalan answers - every single one was correct regardless of which agent it landed on. So by answer quality, routing here is effectively 100% in every language; the percentages above are a floor, not the true error rate, since they compare against one fixed "correct" agent label on questions that really do have two right answers. Automating this check for the whole benchmark is future work (§5). This isn't always harmless on other models, though: in the Llama run (§3.3) the router misroutes the *opposite* way, sending ranking questions to the Analysis agent, whose fixed menu can't group-and-rank - producing wrong answers stated with total confidence - a real problem there, unlike the harmless misroutes here.

**Latency:**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 1.12 / 1.37 / 1.71 s | 1.05 / 1.17 / 1.71 s | 1.02 / 1.33 / 1.71 s |
| Full pipeline (DQ/An/Viz) | 3.50 / 3.82 / 4.94 s | 3.18 / 4.15 / 5.36 s | 3.12 / 4.18 / 5.48 s |
| Retry rate | 0% | 0% | 6.7% (Analysis) |

Language makes almost no difference to latency - the real movement is between categories (Visualization is consistently the slowest to narrate), not between languages. The full pipeline is 3-4x the agent-only time everywhere, because it makes three LLM calls (router, agent, narrator) instead of one - the price of the architecture. On a fast hosted model like this, that's a few seconds; on a slow local model it multiplies (§3 has those numbers), so the overhead matters more for a local deployment. All numbers here are machine-dependent, measured on the setup described in §3.2, not tuned hardware.

One number worth calling out on its own, even without a dedicated column: the baseline's Analysis latency in **English specifically** was 5.086s - far above every other cell measured anywhere in this section. Once the scoring bug (§2.2) was fixed, its answer to the t-test question turned out to be a noticeably more complex manual SQL query (per-group mean, count, min, max, and a hand-worked standard deviation via subquery). The Spanish and Catalan baselines never wrote that same elaborate query for the equivalent question - their Analysis baseline latency is closer to 1.6s - a real difference in what the baseline *attempted* by language, even though it landed on the identical 40% correctness everywhere.

**Retries.** Data Query, Analysis, and Visualization share a self-correcting loop (`src/core/retry.py`): the LLM produces a SQL string or JSON plan, it runs, and if it errors, the error is fed back to the LLM and it tries again, up to 3 attempts. "Retry rate" is the fraction of questions where this fired at least once. It never fired on the 55-question English or Spanish benchmarks. Catalan's Analysis category is the only nonzero rate (6.7%) - and it's also the first and only time in this entire evaluation that a retry actually recovered: the plan came back as invalid JSON, the loop retried, and the second try was correct (`attempts: 2`, `correct: true`). The only other place retries ever fired on Anthropic at all was the session with impossible questions (§2.3), where it fired but didn't recover, since a missing column isn't something a retry can fix.

### 2.2 Failure analysis

Before looking at what the 55-question benchmark itself found, two real correctness bugs were caught and fixed while building the Analysis Agent, before any evaluation ever ran - there's no before/after benchmark data for these, since they were already fixed by the time scoring started, but they're worth knowing about because either one would have quietly corrupted results if it had gone unnoticed:

- The regression function used to pick its prediction target by its position in the column list, not by name. Since the LLM naturally lists columns in question order ("predict profit from sales, discount, quantity" puts profit first), this could swap the target and give a low-r² wrong answer, with no error raised to flag it.
- The Analysis Agent could originally only ever `SELECT` whole columns, with no `WHERE` clause at all, so a question with a condition in it (like "average profit in the West region") was computed over the *entire* table instead, again with no error.

Both were fixed by adding an explicit field to the plan (`target`, `filters`) instead of relying on an implicit convention the LLM had no way of knowing about.

The rest of this section covers what the real 55-question benchmark found, in all three languages - every wrong answer this evaluation actually found traces back to one of the causes below, not to the model misunderstanding Spanish or Catalan.

**The "how many orders" problem.** `COUNT(order_id)` gives 9,994 (every line-item row); `COUNT(DISTINCT order_id)` gives 5,009 (real order transactions, since one order can have several line items). Claude always picks the DISTINCT version whenever "orders" is counted, in every language - which even changes who "wins" on "which customer placed the most orders" ("Emily Phan" under DISTINCT vs. "William Brown" under the ground truth's convention). Which specific answer counts as "correct" shifts with which convention the ground truth happened to use, but it's the same scoring mismatch in English, Spanish, and Catalan - not a language-specific mistake. Not affected by the fixes below.

**FIXED: a real limitation in the evaluation's own scoring, not in what the baseline can do.**

*Original finding*: the baseline scorer assumed a plain SQL model could only manage simple statistics like a mean; correlation, covariance, and t-test were marked `incorrect` automatically, regardless of what the baseline actually returned, on the assumption they can't be written as one SQL query. That assumption was wrong: Claude's baseline worked out the exact Pearson correlation formula by hand in SQL and matched the real system's value almost exactly, but was still marked wrong.

*Fix applied*: `check_baseline_analysis` now checks the key number for correlation, covariance, and t-test (e.g. comparing the specific `t_statistic` value against what the baseline returned), instead of auto-rejecting them. Regression, PCA, and K-Means are still auto-rejected, correctly - those need repeated steps or matrix math that one plain SQL `SELECT` can't do. That's a real limit of SQL, not an assumption in the scorer. This fix isn't specific to any one language - it changes how every language's baseline is scored, equally.

*Effect, confirmed by the re-run*: baseline Analysis correctness in English went from 20.0% to 40.0% - not because the baseline got better, but because it was always this capable and wasn't getting credit (its correlation answers on Q5 and Q13 now score correct, with no change to what it actually returns). The fix also still works in the other direction: on the t-test question, the baseline wrote an elaborate answer (mean, count, a hand-worked standard deviation for each group) but never computed a real t-statistic, and the fixed scorer still marks this one wrong, exactly as before.

*What the baseline can and can't do*: 3 of the 15 Analysis questions - regression, PCA, K-Means - can't be done in a single SQL query at all: they need many repeated steps, or matrix math, and one `SELECT` can't loop or work through steps like that. This is a limit of the tool, not the model, and it's the same limit in every language. The baseline is scored wrong on all 3 by design. This inflates the raw gap a little: the baseline's ceiling on Analysis is 12/15, not 15/15. On the 12 questions SQL *can* answer, the baseline scores 50% (6/12) in English and architecture value is +50pp, vs. 40% and +60pp over all 15 - both true, same conclusion either way. This only affects the baseline comparison; the monolithic agent has the same Python tools, so the decomposition-value numbers in §2.1 are a clean comparison here.

**The chart grouping problem.** "Line chart of profit over time for the East region in 2017" never says how to group the dates. In **English**, the real Visualization agent and the baseline both grouped by `order_date` (day by day) and were marked wrong against a ground truth grouped by month, while the monolithic agent grouped by month and matched - this one question is the entire -10pp English decomposition value in Visualization at n=10, not a real capability gap. In **Spanish and Catalan**, the real system and the baseline both picked monthly instead, and both passed. So this single ambiguous question flips outcome depending on language, purely by chance of which granularity the model happened to guess - not a real difference in ability.

**Routing errors.** Covered together with the actual numbers in §2.1's routing table above, since the pattern (average/median questions sent to Data Query, not a real error) is identical in all three languages.

**FIXED: `compute_ttest` now compares two groups, not two arbitrary columns.**

*Original finding*: `compute_ttest` ran a t-test between two numeric *columns* directly (e.g. discount vs. profit) - not what a t-test is for; a t-test compares one variable across two *groups*. This had a real effect: Report Agent Session 5 described the result as "a negative correlation," which a t-test doesn't even measure (§2.3 has the full report-level story).

*Fix applied*: `AnalysisPlan` now has explicit `group_column` and `group_values` fields (exactly 2 values), `compute_ttest` splits the data into two real groups, and the benchmark question was rewritten to a real group-comparison question ("is there a significant difference in profit between the Consumer and Corporate segments?"), then translated into Spanish and Catalan the same way as every other question.

*Effect, confirmed by the re-run*: the real Analysis Agent and the monolithic agent both now give the correct result in every language (`t_statistic=-0.856, p=0.392`, group means $25.84 Consumer vs. $30.46 Corporate), matching the ground truth exactly. The regenerated Session 5 (§2.3) confirms the fix worked end to end.

**What's left once the ambiguities above are set aside.** Minor, not worth fixing on their own: `SELECT *` instead of the requested columns; pre-binned histograms as a different (not wrong) way to show the same thing; and the `MAX_ROWS` + `ORDER BY` interaction, where which rows come back depends on sort order once a result passes the 1,000-row cap. Once the how-many-orders and chart-grouping ambiguities are set aside, **the real system is basically 100% correct in all three languages.** The baseline fails on the same questions everywhere, for a structural reason that has nothing to do with language: SQLite has no `MEDIAN`/`STDEV`/`VAR_POP`, and regression/PCA/K-Means can't be done in one `SELECT`. The monolithic agent's few extra misses are the same vague questions in every language ("where does the business perform best," "which segment dominates sales"), plus one Catalan-only JSON parse error.

### 2.3 Report Agent quality

Six sessions, rated by hand on the rubric in §1: five normal sessions, plus one (Session 6) where every question is impossible to answer from the data, to see whether the agent invents a finding rather than saying so. Translations live in the dataset files the same way as the 55 correctness questions; ground truth and system prompts don't change with language (§1). Output is in `results/eval/anthropic/{en,es,ca}/`.

**Normal sessions 1-5, English (the detailed walkthrough - Session 5 re-rated after the t-test fix above).**

| Session | Accuracy | Completeness | No fabrication | Fluency |
|---|---|---|---|---|
| 1 — Data Query, easy | 3/5 | 5/5 | 2/5 | 5/5 |
| 2 — Analysis | 4/5 | 5/5 | 4/5 | 5/5 |
| 3 — Visualization | 5/5 | 5/5 | 5/5 | 5/5 |
| 4 — Mixed, realistic | 3/5 | 5/5 | 4/5 | 5/5 |
| 5 — Mixed, hard | **5/5** | 5/5 | **5/5** | 5/5 |
| **Mean** | **4.0/5** | **5.0/5** | **4.0/5** | **5.0/5** |

Session 5 went from 2/5 to 5/5 on both accuracy and no-fabrication - a direct result of the `compute_ttest` fix (§2.2), not a different reading of the same report. Mean accuracy and no-fabrication across all five sessions rose from 3.4/5 to 4.0/5 because of this one fix. Sessions 1, 2, and 4 weren't touched by the fixes and keep their old ratings: Session 1 makes up a profit-margin number nobody asked for (no-fabrication 2/5); Session 4 has small arithmetic errors and mixes up which turn a number came from.

**FIXED: the Report Agent always answered in English, no matter the conversation's language.** This is what came up when these same 5 sessions were translated and run in Spanish and Catalan.

*Original finding*: everything else in the system followed the conversation's language correctly - questions, per-turn answers, even number formatting ("725.457,82", "-0,219", "9,82 anys"). Only the Report Agent's output, and its "Questions Asked" section, stayed in English every time, even in a Spanish or Catalan session.

*Why this happened*: `generate_report_core(history)` had no language setting at all, and its instructions to the model ("Write a professional report...") are plain English with no mention of language anywhere. The per-turn narrator (`narrate.py`) doesn't have this problem, even though it also has no language setting: it puts the real question text straight into its own prompt ("User question:\n\n{question}"), so the model just naturally answers in the same language as the question. The Report Agent's prompt instead dumps the whole conversation as one block of JSON data - the original-language questions are in there, but buried under English instructions, and the English wins out.

*The fix*: the instructions stay in English, as they should. I added one extra line, built by a new `build_system_prompt(language)` function in `src/agents/report/prompts.py`. When the caller knows the language for sure - the eval scripts always do - that line names it directly ("Write the report in Spanish."). When it doesn't - a real conversation through the REPL, which has no language setting at all - the line instead says "write the report in the same language as the user's questions below." This second case is the one that actually matters for real use: a user who doesn't speak English just types in their own language, with nothing to configure, and needs the report back in that same language. I checked this directly, with no eval script involved at all: I called the Report Agent with a Catalan question and no language given, and it correctly wrote the report in Catalan, from that fallback line alone.

*Checked, then re-run*: I added two new unit tests, one for each of the two cases above. The Spanish and Catalan Report Agent benchmarks (all 6 sessions each) were then re-run on Anthropic with the fix in place, and the results below replace the old English-only ones completely. There's no useful "before" to keep here, unlike the t-test fix above - grading an English report for a Spanish or Catalan session was never measuring anything real to begin with.

**Sessions 1-5, all three languages, after the fix:**

| | EN | ES | CA |
|---|---|---|---|
| Sessions 1–5 mean — Accuracy / Completeness / No-fabrication / Fluency | 4.0 / 5.0 / 3.8 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 |

Sessions 1-5 score a little higher in both new languages than in English. The main reason: the fake profit-margin number that shows up in English Session 1 (above) doesn't appear in either the Spanish or Catalan version, and nothing else got invented in its place. There is one real mistake in both new languages: Session 4's segment breakdown (Consumer/Corporate/Home Office) has the right order counts in both, but the percentages worked out from them are wrong, in two different ways - Spanish's three percentages add up to 110%, Catalan's add up to 91.7%. Just a plain arithmetic mistake by the model each time, not a data problem.

**Session 6: behavior on impossible questions.** This session checks something the other five can't: when an agent fails or is asked for something the data doesn't have, does the Report Agent say so, or invent a finding? All six questions can't be answered from the Superstore data. Rated with a failure-focused template instead of the normal one. English, run first, gets the detailed turn-by-turn walkthrough below; Spanish and Catalan's numbers follow in the same table style as the rest of this section.

**English, in detail:**

| Dimension | Score | Justification |
|---|---|---|
| No fabrication | **2/5** | The report claims Q6's chart "successfully" revealed a positive correlation - a finding no agent computed - and files the impossible request (asked as "employee salary vs profit") as a plain "sales vs profit" analysis, hiding the impossibility. It does *not* invent age or marketing-spend values, and its 2016 figures match the real query rows, so 2, not 1. |
| Failure transparency | **3/5** | Two of three failures (age, marketing spend) are listed with correct reasons. Q5 is handled well. But Q6's impossibility is hidden, and Q1 is described as a "system security restriction" rather than a missing column. |
| Completeness | **4/5** | All six questions are covered. Docked one point since Q6 is shown as something other than what was asked. |
| Fluency | **5/5** | Well structured. If anything, too confident - the made-up correlation reads just like the real findings. |

What each agent did with its turn, in English:

| Q | Asked for | Routed to | What happened |
|---|---|---|---|
| 1 | Average customer age (no such column) | data_query | Errored with the wrong message (`UnsafeSQLError: Only SELECT queries are allowed`) instead of "no such column: age." 3 retries, all rejected. |
| 2 | Sales for customer "Jonathan Q. Fakename" (doesn't exist) | data_query | Correct - null result, narration says the customer may not exist. |
| 3 | Correlation of "marketing spend" with profit (no such column) | analysis | Planner used `sales` instead, then broke its own JSON with an extra note, failing with a `ValueError` after 3 retries. Would have called a sales-vs-profit correlation "marketing spend" if the JSON had been clean. |
| 4 | Orders shipped to Germany (data is US-only) | data_query | Correct - returns 0, though the narration doesn't mention the data is US-only. |
| 5 | "Why did profit decline in 2016?" (false premise) | data_query | Best handling of the six: pushed back ("I cannot confirm that profit declined overall in 2016"), gave real monthly numbers, said 2015 data would be needed. No made-up answer. |
| 6 | Scatter of "employee salary" vs profit (no such column) | viz | Chart engine actually plotted `Sales` vs `Profit` (saved file titled "Sales versus Profit per Order"), but the narration kept calling it "Employee Salary" and invented a salary range ($14.62-$957.58). Reported as a success. |

Things worth knowing about English's Session 6:

- The main problem happens earlier in the pipeline: the Data Query and Analysis planners substitute `sales` for a missing column (Q3, Q6). The Report Agent mostly just repeats what it's given.
- The Report Agent is actually more grounded than the narration - for Q6 it used the real chart data (labelled Sales/Profit) and avoided the "employee salary" mistake, but still didn't say the request was impossible, and added an uncomputed "positive correlation" claim.
- The retry loop ran for the first time here (Q1, Q3, `attempts: 3`) but couldn't recover, because a missing column isn't a syntax error a retry can fix.
- For the clearest cases (age, marketing spend, missing customer) the report invents nothing. The risk is specifically when an agent half-answers with a substituted column and passes up a normal-looking result.

**Session 6, all three languages:**

| | EN | ES | CA |
|---|---|---|---|
| No-fab / Failure-transparency / Completeness / Fluency | 2 / 3 / 4 / 5 | 4 / 3 / 5 / 5 | 4 / 3 / 5 / 5 |

Spanish and Catalan both score better on no-fabrication, but for a reason that has nothing to do with the language fix above: the per-turn narration for Q6 was already better in those two languages, in the original evaluation before the fix too. The English chart turn invents a fake "employee salary" label and a made-up correlation; the Spanish and Catalan narration correctly describes it as a sales-vs-profit chart instead. That difference lives in the turns, not the report, so it shows up the same way now that the report is finally written in the right language. Failure-transparency stays at 3/5 in every language, for the same reason each time: Q1's answer ("9.84 years" in English, "9,82 anys" in Catalan - really the average *order* age, not customer age, an odd result the narration itself already flags, unrelated to the language fix) gets turned by the report into a finding about how old the data is, instead of being stated plainly as something the system can't answer. Q3's marketing-spend correlation is the only one of the three impossible questions each report, in every language, handles honestly by saying it failed.

### 2.4 What Anthropic's results show, overall

- The system handles Spanish and Catalan about as well as English - correctness, routing, and latency all close to English, and every wrong answer traces to one of the two already-known ambiguities, not language misunderstanding.
- The one real gap found here - the Report Agent always writing in English regardless of conversation language - was fixed after this evaluation and independently re-verified above; the numbers already reflect the fix, not the original bug.
- This was one model, one set of translations, done by me and not independently checked.
- A real correctness bug (`compute_ttest`) and a real evaluation scoring limitation were found, fixed, and independently verified at three levels (unit test, integration test, regenerated report) - a real example of the evaluation process catching and fixing real problems, not just producing a number.
- Anthropic is treated as the main, most relevant model in this evaluation throughout the rest of this document - the largest one tested, and the one these results show performing most solidly.

---

## 3. The local models: Llama, Salamandra, and why not Groq

### 3.1 Why Groq isn't one of them

I tried to run the evaluation on Groq, but ran into real infrastructure problems that made it impractical to finish. The model I originally planned to use (`llama-3.3-70b-versatile`) was retired by Groq mid-project, so I switched to its closest replacement (`openai/gpt-oss-120b`). On the free tier, that replacement's daily token limit turned out to be far too tight for this evaluation: a single benchmark run, in a single language, used almost the entire 200,000-token daily allowance by itself. At that rate, finishing even an English-only run would mean waiting for the quota to reset and resuming several more times; matching the same three-language depth I have for Anthropic and Llama would realistically take 1.5-3 weeks of repeating that every day. I looked into paying for Groq usage, the same way I already do for Anthropic, to remove the daily limit - but Groq's paid tier signup is currently disabled ("temporarily unavailable due to high demand"), which also appears to be a wider, ongoing issue other users are reporting, not something specific to my account. Given this, I decided not to pursue a Groq run any further. No Groq numbers are reported anywhere in this document.

Instead, my supervisor suggested trying another model to run locally through Ollama - either one built for these specific languages, or a much smaller one, to see what changes. I picked **Salamandra-7b-instruct** (Barcelona Supercomputing Center), for a specific reason, not just because it was suggested: it's almost the same size as `llama3.1:8b` (7.77B vs. 8B parameters), so switching to it isolates one thing - what the model was trained on - instead of also changing model size at the same time. §3.4 explains this choice in full, and what came of it. (§1 has a quick side-by-side of all three models as models, if you want the specs before reading further.)

### 3.2 Shared infrastructure notes (both local models run through Ollama)

- **Anthropic** - fast, reliable, no rate-limit trouble. Costs money per token (small here, but real).
- **Local models (Llama, Salamandra), via Ollama** - free and private, but slow on a normal laptop (CPU only): ~12-20s per question once warm, 160-340s to load the model the first time, several hours for a full run, CPU at 100% the whole time.

**What a "warm-up" call is, and why it only matters for Ollama.** Before timing real questions, the benchmark sends one throwaway question through the same code first, uncounted (`src/eval/utils/warmup.py`) - because Ollama has to load the whole model into memory the first time it's used, which takes 160-340 seconds on its own and has nothing to do with actually answering. Without a warm-up, that cost would land inside the first timed question and make it look far slower for no real reason.

I found this while testing Llama, before the full evaluation and before Salamandra was ever added to the project: with no warm-up at all, the first question in a run was taking much longer than the rest, which mattered since latency is one of the things this project measures. My first fix used a warm-up question unrelated to the real ones, and it didn't work - the first real question was still slow, as if nothing had warmed up. Only a warm-up that went through the *exact same code path* as the real questions (same function, same kind of prompt) actually fixed it. So a warm-up only pays the loading cost if it exercises the same path as what's about to be timed. This only matters for Ollama, since it loads a model locally. Anthropic is a hosted API with nothing to load, and its numbers show no such pattern - the first question in a run isn't slower than the rest.

**A second real Ollama-only bug, found while re-running the Report Agent benchmark on Llama after the language fix (§3.3): nothing was limiting how many tokens one answer could generate.** `ChatOllama` was set up with no `num_predict` value, so Ollama used its own default instead - which turned out to be about 40,960 tokens, basically no limit at all. On one adversarial-session report, the model never produced a stop token, and the call kept running on CPU for over 5 hours before I killed it by hand. I checked it wasn't just frozen by asking the local server directly (`llama.cpp`'s `/slots` endpoint): it was still actively generating the whole time, just with nothing telling it when to stop. Fixed by setting a cap of `num_predict=2048` for Ollama in `src/llm/factory.py` (Ollama only - every real answer here, a SQL query, a JSON plan, a report, easily fits under that; Anthropic and Groq don't use this setting and aren't affected). I ran the same session again afterward and it finished normally in a few minutes.

The Llama run was done in stages, with breaks between them to keep the laptop from overheating during multi-hour runs.

### 3.3 Llama 3.1 8B

**Correctness, by language:**

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" = monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 83.3% | 43.3% | 80.0% | 76.7% | 36.7% | 80.0% | 70.0% | 26.7% | 60.0% |
| Analysis | 100% | 33.3% | 80.0% | 93.3% | 20.0% | 40.0% | 93.3% | 20.0% | 33.3% |
| Visualization | 100% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% |

The real system stays close to Anthropic even on this much smaller local model (70-100% vs. 90-100%), and does better on Visualization in all three languages. The baseline is much weaker on Data Query (27-43% vs. Anthropic's 77%): a small model writing raw SQL with no tools makes real mistakes, not just the counting problem below. Correctness drops a little from English to Spanish to Catalan, most visibly on Data Query (83 → 77 → 70%) and the monolithic agent (80 → 80 → 60%) - likely just normal noise from a small model, since the actual mistakes are the same kind in all three languages (below).

**Routing - the real weak point:**

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 56.4% | 50.9% | 52.7% |
| Data Query | 20% (6/30) | 20% (6/30) | 20% (6/30) |
| Analysis | 100% | 86.7% | 86.7% |
| Visualization | 100% | 90% | 100% |

**Data Query routing is stuck at exactly 20% in all three languages**, almost all misrouted to Analysis (24/24 in English; 23/24 in Spanish and Catalan, a few going elsewhere). This model can't reliably tell "retrieve/aggregate with SQL" apart from "compute a statistic" - the opposite of Anthropic's routing gap (§2.2). **And this time it's not a harmless mix-up.** Checking what actually happened: of English's 24 misroutes, 9 errored outright, and only 2 of the remaining 15 landed on the right answer - e.g. correctly naming "Consumer" as the biggest segment, but giving an average instead of a total. The rest are just wrong, stated as if right (e.g. "the business performs best in the South region," when it's the West). Spanish and Catalan show the same pattern. The Analysis agent's fixed menu can't group-and-rank, so unlike Anthropic's misroutes, these are answers a real user would see and believe - not just a scoring technicality. The misrouting also causes outright pipeline failures: 10/55 (EN), 8/55 (ES), 11/55 (CA), almost always because a Data Query question reached Analysis and it couldn't handle it (`no such column`, `No numeric columns found`, `Unknown analysis 'sum'` - the model making up an analysis type that isn't in the menu).

**Failure analysis - mostly the same mistakes in all three languages.** The Data Query agent repeats the same mistakes across all three languages - real weaknesses of the model, not translation artifacts:

- **"Revenue" confused with "profit"**: `SUM(profit)` written where the question asks for revenue - in all three languages ("who generated the most revenue", "product with the most revenue").
- **Min/max of one row instead of grouping first**: e.g. `MIN(profit)` or `MAX(quantity)` on the raw table instead of grouping by region/product first, then taking the min/max of the totals - for "least profitable region" and "product with the most units sold," all three languages.
- **Correct query, missing `LIMIT 1`**: returns every row instead of the top one - English and Catalan.
- **Wrong column for "how many customers/purchases"**: Spanish used `COUNT(*)` instead of `COUNT(DISTINCT customer_id)`; Catalan summed `quantity` instead of counting orders at all.

Catalan also has two mistakes not seen elsewhere:

- **Region confused with State.** Twice, a question naming "state" got grouped by `region` instead - two different location columns mixed up, not just a wrong aggregate.
- **Picking the wrong replacement analysis.** Asked to cluster orders into 3 groups, the model noticed "groupby" wasn't a valid option, then guessed an unrelated replacement ("describe," a simple summary) instead of the actual K-Means option - and broke its own JSON output explaining the swap. Happened on the same clustering question in both Session 5 and the standalone benchmark.

One possible language-sensitive slip: Spanish "¿cuál es el descuento **medio**?" (average) was planned as `median` - "medio" and "mediana" may have been confused. Catalan's impossible age question also reasoned that age could be "approximated by the average order date" - a real attempt at a workaround rather than a refusal, that then failed on an unrelated JSON formatting error. The one Visualization miss per language is the familiar chart-grouping problem (§2.2) - all three languages (and Anthropic, §2.2) show different granularity guesses on the same chart question, which never says how to group the data. Spanish and Catalan both grouped by *year*, an even coarser guess than daily or monthly.

**Latency:**

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 12.5 / 13.7 / 19.8 s | 9.3 / 13.1 / 19.7 s | 12.4 / 16.7 / 16.3 s |
| Full pipeline (DQ/An/Viz) | 54.9 / 65.8 / 129.3 s | 44.5 / 62.3 / 143.8 s | 71.9 / 46.6 / 71.5 s |
| Retry rate | DQ 3.3%, Viz 10% | DQ 6.7%, Viz 10% | Analysis 6.7% (failed) |

10-25x slower than Anthropic, expected for local CPU inference. A full run took several hours per language, mostly from this per-question slowness plus the model-loading warm-up cost (§3.2). Catalan also had the most pipeline failures of the three languages (11/55, vs. 8/55 Spanish and 10/55 English). This doesn't affect correctness, only how many pipeline calls errored.

**Report Agent, re-run after the language fix (same bug and fix as Anthropic's, §2.3).** The Report Agent's output was always in English no matter the session's language, on all three models tested, since the code had no language setting for it at all. This section shows what the same fix did to Llama's numbers (§3.4 has Salamandra's). One extra problem turned up while re-running this on Llama: the Spanish Session 6 re-run got stuck for over 5 hours generating a single response, before I killed it and found the real cause - the missing token limit described in §3.2. Fixed at the same time as the language bug, then re-run cleanly.

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN, unaffected by the language fix), Spanish (ES), Catalan (CA).**

| | EN sessions 1-5 mean | ES sessions 1-5 mean | CA sessions 1-5 mean |
|---|---|---|---|
| Accuracy / Completeness / No-fab / Fluency | 3.0 / 5.0 / 4.2 / 4.6 | 3.0 / 5.0 / 5.0 / 4.8 | 3.4 / 5.0 / 5.0 / 4.8 |

| Session 6 (impossible questions) | No-fab | Failure-transp. | Completeness | Fluency |
|---|---|---|---|---|
| EN | 1 | 2 | 4 | 4 |
| ES | 1 | 2 | 4 | 4 |
| CA | 2 | 2 | 5 | 4 |

Accuracy stays low in both languages, for the same reason as before this fix: Llama's weak routing (above) sends several questions to an agent that can't really answer them, and the report just repeats a wrong or incomplete answer without adding anything made up of its own - that counts against accuracy, not against no-fabrication (§1 explains the difference). One new mistake turned up this time, and it's different from the rest: in Spanish Session 3, the chart turn itself correctly says Technology has the highest category sales ("la categoría de tecnología generó las ventas totales más altas") - but the Report Agent's own summary gets it wrong anyway, crediting Furniture instead. Unlike everything else in this section, that mistake is the Report Agent's own, not something it copied from a bad answer.

No-fabrication for sessions 1-5 is better than the old English numbers, in both new languages - the wrong-answer cases from the routing problems above don't come with any extra made-up detail added on top this time. Session 6 tells a different story, and shows the worst problem found here isn't about report language at all: asked for the correlation between "marketing spend" and profit (a column that doesn't exist), the Analysis Agent quietly uses `discount` instead and reports a precise, confident correlation as if it were the real answer - `-0.219` in Spanish, `-0.22` in Catalan - in both new languages, exactly like before this fix. Every Anthropic run on this same question either failed with an error or refused to guess (§2.3). Spanish adds a second made-up claim on top: its report also says there is a "negative relationship" between the (made-up) "employee salary" and profit in the Q6 chart - but that chart doesn't show any such relationship either way, since it's really sales vs. profit. Catalan's report describes the same chart without making up a direction for the relationship.

**What Llama's results show, overall.** The routing weakness and the marketing-spend fabrication above are two findings with no equivalent on Anthropic - real differences in what the models can do, since everything else about the pipeline is identical. Translations for all three languages, on all three models in this document, are one pass done by me, not independently checked.

### 3.4 Salamandra 7B Instruct

**Why it was picked, and what I expected going in.** Meta's own Llama 3.1 model card lists 8 languages it was specifically fine-tuned and safety-tested for: English, German, French, Italian, Portuguese, Hindi, Spanish, Thai. Catalan isn't one of them. But the model card also says plainly that "Llama 3.1 has been trained on a broader collection of languages than the 8 supported languages" - so this isn't "the model doesn't know Catalan," it's "Catalan didn't get the same dedicated fine-tuning attention as those 8." That matches what §3.3 already found: Llama clearly has real, working Catalan ability, just somewhat weaker than English or Spanish. Salamandra was built specifically to close gaps like this one: trained on 35 European languages, with Spanish, Catalan, Galician, and Basque oversampled 2x, by a public research center whose whole purpose is covering languages general models under-serve. Picking it at almost exactly Llama's size (7.77B vs. 8B parameters) was deliberate, so that switching models changes what the model was trained on and nothing else. Going in, the expectation this was meant to test was simple: if a model is specifically trained on Spanish and Catalan, its behavior in those two languages should be at least as reliable as in English, closing (or at least explaining) the small English-to-Catalan decline Llama showed.

**What actually happened was the opposite of that, and it surprised me.** Salamandra was not more reliable in Spanish and Catalan - if anything, its worst and strangest failures happened specifically in those two languages, not in English. The details are below, but the headline finding first: **language-specific training data did not translate into more reliable behavior in that language, at least not for this model at this size.** What follows is everything that led to that conclusion.

**Correctness and routing, by language:**

**Model: Salamandra-7b-instruct (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" = monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 63.3% | 43.3% | 26.7% | 53.3% | 36.7% | 20.0% | 56.7% | 36.7% | 26.7% |
| Analysis | 80.0% | 13.3% | 33.3% | 86.7% | 20.0% | 26.7% | 80.0% | 13.3% | 46.7% |
| Visualization | 50.0% | 50.0% | 70.0% | 50.0% | 40.0% | 60.0% | 40.0% | 50.0% | 60.0% |

The core claim of this whole project holds up even on this weaker model: on Data Query and Analysis, the real agent clearly beats the baseline in every language - the multi-agent design still adds value when the underlying model makes far more mistakes overall than Anthropic or Llama. Visualization breaks that pattern, but not in one consistent direction: the baseline ties the real agent in English, loses to it in Spanish, and beats it in Catalan - no reliable architecture value either way. The monolithic agent, though, beats both the real agent and the baseline in every language. Data Query and Analysis also show the monolithic agent doing *worse* than the agent alone in every language - the opposite of what Anthropic and Llama showed, where the monolithic agent stayed close to the specialized agent. Combining all three system prompts into one call appears to cost this particular model more than it costs the other two.

**Routing accuracy:**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 78.2% | 78.2% | 74.5% |
| Data Query | 70.0% | 96.7% | 96.7% |
| Analysis | 80.0% | 26.7% | 13.3% |
| Visualization | 100% | 100% | 100% |

Data Query routing gets *better* in Spanish and Catalan than in English (70% to 96.7%), while Analysis routing falls apart in those same two languages (80% down to 26.7%, then 13.3%). Checking exactly where those Analysis questions went: every single one was sent to Data Query instead (11/11 in Spanish, 13/13 in Catalan). This is close to a mirror image of Llama's weak point, which was Data Query stuck at 20% in every language while Analysis stayed strong - the two local models fail at routing in close to opposite directions.

**Correctness failure analysis.** Reading through the actual wrong answers (not just the accuracy percentages), Salamandra's Data Query mistakes look different from Llama's - less "wrong column," more "wrong shape of answer":

- **Answering "how many" with a list instead of a count.** For "How many distinct product names are there?" and "How many unique cities are represented?", the model wrote `SELECT DISTINCT product_name FROM orders` (or `city`) - a query that lists every value instead of counting them. Technically related to the question, but not an answer to it.
- **Wrong aggregate for "how many customers."** `COUNT(*)` (every row) instead of `COUNT(DISTINCT customer_id)` - the same specific mistake Llama's Spanish run made, here happening on Salamandra too.
- **An unwanted `GROUP BY` on a single-number question.** Asked for "the total profit" - one number - the model wrote a query that grouped by region instead, returning several numbers instead of one.
- **Missing `DISTINCT` on a "list all" question.** "List all product categories" came back as one row per order instead of the short list of unique categories.
- **Confusing clustering with PCA.** Asked to "cluster orders into 3 groups," the Analysis planner picked `pca` (a different technique - one reduces dimensions, the other groups rows) instead of `kmeans`. The same mix-up shows up again inside the Report Agent findings below.

These same kinds of mistakes appear in Spanish and Catalan too, not just English - a real weakness of the model, not a translation issue.

**By difficulty, added across all three languages (30 easy/medium/hard-tagged answers per row for Data Query and Analysis, since each language has 10; Visualization has 9 per tier from 3x3):**

| | Easy: real / base | Medium: real / base | Hard: real / base |
|---|---|---|---|
| Data Query | 46.7% / 56.7% | 43.3% / 30.0% | 83.3% / 30.0% |
| Analysis | 44.4% / 11.1% | 100% / 33.3% | 83.3% / 0% |
| Visualization | 100% / 100% | 33.3% / 41.7% | 11.1% / 0% |

This is the one place Salamandra's numbers don't match the pattern seen on the other two models: **Data Query "hard" (83.3%) scores much better than Data Query "easy" (46.7%)** - the opposite of what difficulty tags are supposed to predict, and the opposite of Anthropic's and Llama's own difficulty tables (§4.2 discusses this further). Analysis and Visualization behave more as expected, dropping (or staying flat) from easy to hard.

**Latency, and a hardware note:**

**Model: Salamandra-7b-instruct (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 12.6 / 15.2 / 26.3 s | 9.9 / 15.2 / 23.0 s | 8.9 / 16.3 / 31.8 s |
| Full pipeline (DQ/An/Viz) | 31.0 / 85.1 / 155.1 s | 30.0 / 86.7 / 54.8 s | 40.6 / 102.5 / 77.0 s |
| Retry rate | DQ 0%, Viz 6.7% | DQ 0%, An 6.7%, Viz 6.7% | DQ 3.3%, An 6.7%, Viz 3.3% |

Slower than Llama across the board despite a close parameter count, and Visualization's full-pipeline time swings a lot between languages (155s in English, 55s in Spanish, 77s in Catalan) - on this hardware, that is at least as much about the machine as about the model. The laptop used for every Ollama run has only 7.4GB of RAM and no GPU, and was measurably swapping memory to disk during these runs. One call during the Catalan correctness benchmark failed with `ResponseError: model runner has unexpectedly stopped` - a one-off crash, not a repeating pattern, and consistent with running a model this size on a machine this tight on memory rather than a problem with the model itself.

**The Report Agent: a number that would not go away.** This is where the "surprised me" part of this section really shows up. Reading the actual reports (not just checking their language) turned up something more specific than "the model makes mistakes": the same wrong numbers show up for different questions, in different sessions, in all three languages.

*`108,418.4489`.* This exact figure appears as the answer to "What is the total profit?" (Session 1, all three languages - the correct value, used everywhere else in this document, is $286,397.02) *and* as the answer to "What is the average profit in the West region?" (Session 2, all three languages - the correct value is $33.85). Two different questions, three languages, one number, and it matches neither correct answer. This didn't come from the Report Agent - it is already in the underlying Data Query turn - but it shows up unchanged across every language this evaluation tested, which points to a problem in how this model generates SQL for these two questions, not a translation issue.

*`42.5` years old.* Session 6 asks "What is the average age of our customers?" - a question this system cannot answer at all, since there is no age column (every other model either refuses or returns a clearly broken number tied to order dates, e.g. Anthropic's "9.84 years," §2.3). Salamandra's own turn gives three different numbers across the three languages (35 in English, 34.67 in Spanish, 30 in Catalan) - but the *Report Agent*, writing the final summary, states "42.5 years" in all three languages regardless of what its own turn said. That is not a rounding difference or a translation slip: it is the same specific, wrong, made-up number appearing three separate times, replacing three different real inputs.

A related pattern shows up more than once: a real number from one turn gets reused as the answer to an unrelated question. Session 6 asks for the total sales of a customer who does not exist ("Jonathan Q. Fakename") - the correct behavior, seen from other models, is to report no data found. Salamandra's own turn does this correctly in Spanish ("not available in the data provided"), but the Report Agent's Spanish and Catalan summaries both state the answer as `725457.8245` or `725457,8245` - the exact total sales figure for the West region, used earlier in the same session for a completely different question, presented now as a specific customer's sales total.

These examples (and others like them in the full session data) point to something more specific than "the report sometimes gets facts wrong": in several cases, the model appears to reuse a plausible-sounding number it has produced elsewhere, rather than either computing the right one or admitting it does not have one. This matters beyond Salamandra specifically, since the same failure mode - reusing an unrelated real number as if it answers a different question - was not seen on Anthropic or Llama.

The other finding worth naming directly: **whenever the underlying turn honestly says it does not know something, the Report Agent's summary is the part most likely to replace that honesty with a confident, invented answer.** In the Session 6 examples above, the turns say "not available," "not clear," or fail outright with a real error - and the report each time supplies a specific number anyway. The reverse also happens at least once: Session 3 in English has three visualization turns that either fail outright or return no usable content, and the report still describes specific chart findings ("the Furniture category had the highest total sales," "sales were relatively stable... with a slight increase in the second quarter") that were never computed. Session 3 in Spanish, facing the same kind of failed turns, instead produces a completely empty report (just the four section headers, no content) - the opposite failure, but still not a useful report.

**On top of the number problem, the language fix (§2.3) does not hold as well here as it did for Anthropic and Llama 3.1 8B.** Checking every report's actual body text, not just its header: **3 of the 5 normal Catalan sessions (1, 2, and 4) come back as complete reports written entirely in English**, despite the language-matching instruction being sent exactly as it was for the other two models. Only sessions 3 and 5 are actually written in Catalan. Where the report is in the right language, section headers are still sometimes left half-translated ("Preguntas Asked," mixing an English word into a Spanish sentence) - something that did not happen with either of the other two models tested.

**Report Agent ratings.** I graded accuracy, completeness, and no-fabrication for every session, since those are about whether the facts are right and don't depend on which language they're stated in. But I did not fold the 3 English-language Catalan sessions into a "Catalan quality" mean - that would quietly average in reports that never attempted Catalan at all, which isn't a meaningful number. The Catalan mean below uses only the 2 sessions that were actually written in Catalan; the 3 English ones are counted and explained above instead of graded as if they were a fair Catalan attempt.

Same 6 sessions and rubric as the Anthropic and Llama reviews above.

**Model: Salamandra-7b-instruct (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA, actual-Catalan sessions only, n=2 of 5 - see above).**

| | EN sessions 1-5 mean (n=5) | ES sessions 1-5 mean (n=5) | CA sessions 1-5 mean (n=2) |
|---|---|---|---|
| Accuracy / Completeness / No-fabrication / Fluency | 2.2 / 4.0 / 3.8 / 4.2 | 2.6 / 3.6 / 4.2 / 3.0 | 2.5 / 4.5 / 3.0 / 4.5 |

| Session 6 (impossible questions) | No-fab | Failure-transp. | Completeness | Fluency |
|---|---|---|---|---|
| EN | 1 | 2 | 4 | 4 |
| ES | 1 | 1 | 5 | 4 |
| CA | 1 | 1 | 5 | 4 |

(Session 6 is actually written in Catalan in the CA run, so that row doesn't have the same problem - it's the full n=1 adversarial session, same as for the other two models.)

Accuracy is the lowest of any model tested, in every language, for two different reasons: some answers are wrong because the underlying SQL or analysis step is wrong (the same kind of mistake seen on Llama), and some are wrong because the Report Agent changes a number that its own input turn already got right, for no clear reason (in the English Session 4, the turn names the wrong top-profit category and the report substitutes the correct one anyway - not a fix, just a different guess that happened to land right). No-fabrication is the weakest score of any model on Session 6 specifically, for the reason detailed above: this is the model most likely to turn an honest "I don't know" into a confident, wrong answer.

**What Salamandra's results show, overall.** It adds a third, different set of weaknesses on top of Anthropic's and Llama's, rather than repeating either one - the recurring wrong numbers and the reused-answer pattern above have no equivalent on the other two models. And on the specific question it was added to answer - does language-specific training produce more reliable behavior in that language - the answer is no, not for this model: its worst failures happened in Spanish and Catalan, not English. §4.2 returns to this as one of the main conclusions of the whole evaluation.

### 3.5 Comparing all three models

**By architecture design (does splitting the work up help on its own?).** This is different from "beats a plain baseline" - it's real system vs. the monolithic agent, same tools and prompts, one agent instead of several (decomposition value, §1). Real system minus monolithic, in percentage points:

| | Data Query EN/ES/CA | Analysis EN/ES/CA | Visualization EN/ES/CA |
|---|---|---|---|
| Anthropic | +3.3 / +6.7 / +6.7 | +20.0 / +6.7 / +13.3 | -10.0 / 0 / 0 |
| Llama | +3.3 / -3.3 / +10.0 | +20.0 / +53.3 / +60.0 | +10.0 / 0 / 0 |
| Salamandra | +36.6 / +33.3 / +30.0 | +46.7 / +60.0 / +33.3 | -20.0 / -10.0 / -20.0 |

Splitting the work up helps almost everywhere, but far more on the two local models' Analysis category (up to +60pp) than on Anthropic (modest, 0 to +20pp) - splitting the "which statistic do I compute" decision out into its own agent matters much more for a small model, which has less room to juggle several tool sets in one prompt. Salamandra shows this most strongly of all three: its Data Query and Analysis decomposition values are the largest in the whole table, while its Visualization value is negative in every language - the split helps most on exactly the categories where this particular model struggles most on its own. The two negative numbers on the other models (Anthropic Visualization English, from the chart-grouping question in §2.2; Llama Spanish Data Query, -3.3pp) are single questions flipping at small n, not real reversals.

**By routing.** Overall: Anthropic 90.9-92.7% across languages, Llama 56.4% (EN), 50.9% (ES), 52.7% (CA), Salamandra 78.2% (EN), 78.2% (ES), 74.5% (CA) - and each of the three models fails in a different place:

| | Anthropic EN/ES/CA | Llama EN/ES/CA | Salamandra EN/ES/CA |
|---|---|---|---|
| Data Query | 100 / 100 / 96.7% | 20 / 20 / 20% | 70.0 / 96.7 / 96.7% |
| Analysis | 66.7 / 73.3 / 73.3% | 100 / 86.7 / 86.7% | 80.0 / 26.7 / 13.3% |
| Visualization | 100 / 100 / 100% | 100 / 90 / 100% | 100 / 100 / 100% |

Anthropic's weak spot (Analysis) barely matters - every misrouted question still got answered correctly by whichever agent got it (§2.1, §2.2). Llama's weak spot (Data Query, stuck at exactly 20% in every language) is not harmless - most misrouted questions come back wrong, stated as if correct (§3.3). Same *kind* of mistake (mixing up two similar categories), very different consequences. Salamandra's weak spot is Analysis, and it gets worse outside English (80% down to 13.3% in Catalan) rather than staying constant like Llama's Data Query problem - every one of those misroutes lands on Data Query instead (§3.4).

**By latency.** Full-pipeline average (DQ/An/Viz), seconds:

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 |
| Llama | 54.9 / 65.8 / 129.3 | 44.5 / 62.3 / 143.8 | 71.9 / 46.6 / 71.5 |
| Salamandra | 31.0 / 85.1 / 155.1 | 30.0 / 86.7 / 54.8 | 40.6 / 102.5 / 77.0 |

Both local models are roughly 10-40x slower than Anthropic, expected for CPU-only inference instead of calling a hosted API. Language barely changes Anthropic's latency; both local models' numbers move around more between languages (e.g. Salamandra's Visualization time nearly triples from Spanish to English) - on this machine, that looks more like ordinary variation in the laptop's own state than a real language effect (§3.4).

**On retries.** Fires far more often on both local models (3.3-10% in at least one category per language for Llama, similar for Salamandra) than on Anthropic (once, ever, in the entire evaluation, and it fixed itself) - a smaller model produces more broken SQL/JSON to begin with. It's also less reliable once triggered: some Llama retries fix the problem (English Visualization, 100% success), some don't (the K-Means/"describe" mix-up in §3.3 survived a retry and still failed). Real help on the weaker models, but not a substitute for actually understanding the question.

**On honesty (Report Agent).** Same rubric, all three models, normal sessions 1-5:

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 4.0 / 5.0 / 3.8 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 |
| Llama | 3.0 / 5.0 / 4.2 / 4.6 | 3.0 / 5.0 / 5.0 / 4.8 | 3.4 / 5.0 / 5.0 / 4.8 |
| Salamandra | 2.2 / 4.0 / 3.8 / 4.2 | 2.6 / 3.6 / 4.2 / 3.0 | 2.5 / 4.5 / 3.0 / 4.5 (n=2, not 5 - §3.4 explains) |

Salamandra's CA column here is thinner than the others - 3 of its 5 Catalan sessions came back written in English, so they aren't counted as Catalan quality at all (§3.4).

Surprising: Llama's no-fabrication score on normal sessions isn't worse than Anthropic's, sometimes a touch better - the accuracy gap is a routing problem, not an honesty problem: several Llama sessions ask the Analysis agent something it simply can't do (§3.3), and the report faithfully relays that wrong answer without inventing anything. The picture flips on the session with impossible questions, where every question truly can't be answered: Llama's no-fabrication score (1-2 across languages) drops below Anthropic's (2-3), with a confident, precise, invented correlation number in all three languages, a complete answer made up for a turn that had actually failed, and sample rows mislabeled as computed statistics (Catalan). Salamandra's Session 6 no-fabrication score is just as low, or lower, in every language - and worse in one specific way neither Anthropic nor Llama showed: the same wrong number standing in for different real answers across all three languages (§3.4). So a model can look equally honest on ordinary questions and still be much more willing to make something up the moment there is really nothing true to say - and which specific way it does that varies by model.

---

## 4. Conclusions

### 4.1 What's established, with real evidence

- The specialized multi-agent architecture beats a minimal no-tools baseline, clearly, across all three categories, on Anthropic (§2.1).
- It also beats a monolithic agent with the same tools and prompts, on Anthropic (decomposition value: Data Query +3.3pp, Analysis +20.0pp, Visualization -10.0pp - the last one is entirely one unclear question, §2.2). This compares the monolithic agent against **individual agents in isolation** (routing forced correct), so a fairer end-to-end comparison (routing errors included) is future work (§5).
- A real correctness bug and a real evaluation scoring limitation were found, fixed, and independently verified at three levels (unit test, integration test, regenerated report) - a real example of the evaluation process catching and fixing real problems, not just producing a number (§2.2).
- Routing errors on Anthropic are concentrated at the Data Query/Analysis overlap (simple aggregates), not random (§2.2).
- **The architecture beats the baseline on two much weaker models too** (Llama, all three languages, §3.3; Salamandra, all three languages, §3.4): Llama's real-system correctness stays within 10-20pp of Anthropic's in English and Spanish, while the baseline is much worse everywhere. But routing quality doesn't transfer - Llama misroutes ~80% of Data Query questions, and unlike Anthropic's routing gaps, these produce actually wrong answers (§3.5).
- Splitting the work into separate agents helps on all three models, and helps the two weaker, local models far more than it helps Anthropic (§3.5).

### 4.2 Did we get the answers we expected?

**By difficulty - yes, mostly, for two of the three models.** The benchmarks tag each question easy/medium/hard, and correctness by that tag was already in the raw output (`summary.csv`) but never pulled together for Anthropic and Llama until this section:

| | Easy: real / base | Medium: real / base | Hard: real / base |
|---|---|---|---|
| Anthropic - Data Query | 90.0% / 73.3% | 96.7% / 80.0% | 100% / 76.7% |
| Anthropic - Analysis | 100% / 33.3% | 100% / 66.7% | 100% / 16.7% |
| Anthropic - Visualization | 77.8% / 66.7% | 100% / 75.0% | 88.9% / 22.2% |
| Llama - Data Query | 90.0% / 60.0% | 73.3% / 30.0% | 66.7% / 16.7% |
| Llama - Analysis | 88.9% / 44.4% | 100% / 38.9% | 94.4% / 0% |
| Llama - Visualization | 100% / 100% | 100% / 75.0% | 77.8% / 33.3% |

(Salamandra's own by-difficulty table is in §3.4 - it wasn't run back through this exact cut of the data until later, so it's shown separately rather than added to this one.)

The expected pattern mostly held: **the baseline loses the most ground on hard questions** - exactly where the architecture earns its keep the most. Anthropic's baseline drops to 16.7-22.2% on hard Analysis/Visualization while the real system stays at 88.9-100%; same shape on Llama, lower floor (0-33.3% baseline). But the Analysis "hard" collapse is mostly about labeling, not pure difficulty - the hard-tier questions are exactly the ones needing regression, PCA, or K-Means, which SQL can't express regardless of how conceptually hard they are. Data Query and Visualization hard questions are a fairer difficulty test (the baseline *can* attempt them in SQL), and there it still drops (Anthropic roughly flat, 73.3% to 76.7%; Llama 60% to 16.7%, a real decline). Anthropic's real system is barely affected by difficulty at all (88.9-100% at every tier); Llama's real system visibly drops from easy to hard on Data Query and Visualization - a real capability gap for a smaller model. **Salamandra broke this expectation** - its Data Query "hard" tier scored much *better* than "easy" (83.3% vs. 46.7%, §3.4) - the one place in this whole evaluation where the difficulty tag didn't predict the result at all.

**By language - the expected decline showed up on one model, and Salamandra's result was the opposite of what we expected.** There was a real reason to expect a decline from English to Spanish to Catalan: English dominates LLM training text, Spanish has less, Catalan is a minority language with much less available anywhere. Anthropic is flat across all three (§2.1) - correctness, routing, and latency stay within a few points of each other, and every wrong answer traces to the two already-documented scoring ambiguities, not language struggle. So the expected decline doesn't show up on a strong hosted model - it seems to know each language well enough for this closed-world task. Llama does decline in that order on Data Query and the monolithic baseline (§3.3), and its worst fabrications happened on the Catalan run - matching the expected pattern, for what that's worth. But Catalan also had the highest pipeline failure count of the three, so some, but probably not all, of that decline may be hardware rather than language.

Salamandra was added specifically to test this properly (§3.1, §3.4): a model at almost the same size as Llama, but trained with Spanish and Catalan specifically emphasized, should - if the theory is right - show a smaller decline, or none. **It didn't. If anything, it went the other way.** Its worst and strangest behavior - the fixed wrong age ("42.5 years") replacing three different real answers, a real number from one question reused as the answer to an unrelated one, complete reports written in the wrong language despite an explicit instruction to match it - all of this happened in the Spanish and Catalan sessions, not the English ones (§3.4). So the real answer this evaluation found is: **for this task, language-specific training data did not translate into more reliable behavior in that language, at least not for this model at this size.** What seems to matter more, comparing all three models, is how reliably a model follows instructions and stays grounded in what it was actually given - a property that has little to do with which languages it was trained on.

**By model - yes, this is the one expectation that held everywhere, no exceptions.** Every language, every difficulty tier, all three models: **the specialized multi-agent architecture beats a plain single-prompt baseline**, even on the two much smaller, free, local models, both clearly weaker than the hosted one in other ways, and clearly weaker than each other in different categories (§3.5).

### 4.3 Other things we found, not part of the original questions

- **A real bug in the evaluation's own scoring logic**, not just in the system being evaluated - the baseline scorer wrongly assumed correlation/covariance/t-test couldn't be done in plain SQL, when Claude's baseline actually did the math by hand (§2.2).
- **The Report Agent's language bug** - it was the only part of the system that didn't follow the conversation's language, on every model tested, and needed an explicit fix rather than working automatically the way narration does (§2.3).
- **A real infrastructure bug specific to local models** - no limit on how many tokens a response could generate, causing a single call to run for over 5 hours before being caught by hand (§3.2).
- **Splitting work into agents helps weaker models more than strong ones** - not something the original project questions asked about directly, but a clear, consistent pattern once three models of different strength were compared (§3.5).
- **Salamandra's own report-writing habit of reusing a real number from one answer as the answer to a different question** - not fabrication in the usual sense of inventing something from nothing, but recycling something real into the wrong place. Not seen on the other two models (§3.4).

### 4.4 What's still unclear or unresolved

- **The baseline can't do 3 of 15 Analysis questions at all** (regression, PCA, K-Means, §2.2), scored wrong by design. Architecture value is +60pp over all 15, +50pp over the 12 SQL can express; the headline number uses all 15.
- **Retry/self-correction effectiveness on Anthropic specifically** is based on very little data: the 55-question English benchmark never triggered it, so the only two data points are the impossible-questions session (fired but couldn't recover from a missing column) and the Catalan run (the one successful recovery in the whole evaluation, §2.1). Llama and Salamandra fire it far more often and give a clearer picture overall (§3.5), but neither is Anthropic.
- Whether decomposition value would hold at a larger question count than 55.
- **Latency wasn't a focus.** The architecture costs three LLM calls instead of one - a few seconds on a hosted model, much more locally, plus a one-off model-loading cost the first time. All figures are from one modest laptop, not tuned hardware.
- **Cost per provider wasn't measured.**
- **The scoring itself has two known simplifications** (`src/eval/checks.py`): numbers are compared with a fixed 2-decimal tolerance, not true floating-point precision - fine for this dataset's currency and count values, but would need adjusting for a dataset with much smaller or bigger numbers. And row comparison checks numbers and text as unordered sets, so it can't tell two different numeric columns apart if they happen to hold the same values in the same shape - not an issue for this benchmark's questions, but a trickier question set would need a check that understands what each column actually means.
- **Whether Salamandra's odd behavior is specific to this one model, or to small models trained with heavy multilingual oversampling in general** - this evaluation only tested one model of that kind, so it can't tell the two apart.
- Translations for all three languages, on all three models, are one pass done by me, not independently checked.

### 4.5 Scope and deliberate design choices

**Closed-world, and no LLM-written code.** No internet access, no agent writes or runs its own code - full detail in `docs/architecture.md`. Two consequences here: questions needing outside context ("why did sales drop in 2017", "is a 12% margin good," industry benchmarks) are out of scope, and the Analysis Agent can only answer what its 15 pre-written functions cover (§2.2 covers what that means for the baseline comparison).

### 4.6 Bottom line

The architecture's core promise - specialized agents with real tools beat one generic prompt - holds up everywhere this was tested: three languages, three different models. Splitting that same toolset across separate agents helps too, and it helps the weaker models more than the stronger one. What changes between models is everything that follows from those two points: which category the router gets wrong (and how much it costs when it does), how often self-correction is needed, how fast the answer comes back, and how the system behaves when a question truly cannot be answered. A smaller, free, local model is a real option for the core task, but both local models tested here need a better router and much closer supervision of their Report Agent before either could be trusted the way the hosted model was here - and picking a model trained specifically on the target language is not a reliable shortcut to that trust.

---

## 5. Future work

This is the one place in the repo for ideas on what to build or change next. What the system can't currently do is listed separately, in `docs/architecture.md` (Current Limitations) - this section is about fixing or extending those, not restating them.

- **Make the agents actually cooperate.** Right now each agent is independent - the router picks one, it runs, done. They could pass results to each other directly (e.g. Analysis using a Data Query result as input), instead of only ever going through the orchestrator, or a planner could chain several agents for one question.
- **Remember recent turns, not just the current question.** Routing and narration only ever see the current question right now. Using the last few turns (not the whole history) would let the system understand something like "that region," referring back to an earlier answer.
- **More agents, or a wider Analysis Agent.** Add agent types (forecasting, data quality checks, ...), or widen the Analysis Agent's fixed list of 15 functions - for example ANOVA, so it can compare more than the two groups the current t-test is limited to, or paired samples.
- **A real code-generating agent.** A different kind of change from the one above - not more pre-written functions, but letting an agent write and run its own Python code, with no fixed list at all. No agent does this on purpose right now (§4.5): it trades flexibility for safety, a result that's always the same, and answers that can be checked against an exact right answer. This would also close the gap in §2.2 - the single-agent baseline can't answer 3 of the 15 Analysis questions because of the "SQL only, no code" restriction, not because of the number of agents involved; a single agent that could write real Python (e.g. with scikit-learn) wouldn't have that problem. Doing this safely would need real sandboxing (running the generated code somewhere isolated, with no access outside that one task) and a way to still check its answers, since a code-generating agent can't be checked against ground truth as directly as a fixed list of functions can.
- **Score the pipeline answers automatically.** The pipeline benchmark only records routing and latency, not whether the final answer was right. The misrouted questions were checked by hand here (§2.2), but automating it would give a real "routing quality by answer" number, and a fair end-to-end comparison of the monolithic agent vs. the full system as a user hits it (routing mistakes included) instead of vs. the agents with routing forced correct (§2.1).
- **Reduce the Data Query/Analysis routing overlap.** Right now a mean, median, or other simple statistic can be answered correctly by either agent (§2.1, §2.2), so there's no single right routing choice for those questions. Either the two agents' jobs could be split more clearly (e.g. Analysis only handles anything beyond a raw count or sum), or the benchmark's "expected agent" label could allow more than one correct agent per question.
- **Rewrite the benchmark questions that turned out to have more than one fair answer.** Different from the routing overlap above - this is about the question itself not having one single correct answer, no matter who answers it: "how many orders" (§2.2) can mean `COUNT(*)` or `COUNT(DISTINCT order_id)`, both reasonable; the "profit over time" chart never says whether to group by day or month. Either reword these questions to remove the ambiguity, or accept more than one correct reading in the ground truth, so a wrong score reflects a real mistake.
- **A second, harder dataset.** Everything here is on Superstore. A larger or messier dataset - or one with more than one table (e.g. Olist), to test JOIN handling - would show how much of what was found is specific to this one.
- **A general safety net on LLM calls, not just Ollama's token cap.** The runaway-generation bug in §3.2 was fixed by capping Ollama's output length, but nothing currently protects against a similar failure mode on another provider (e.g. a hung connection) - a wall-clock timeout on any LLM call, not just a token limit, would be a more general fix.
- **Finish the cross-provider picture** - a real Groq run, if its paid tier ever reopens (the free tier's daily token limit makes a full run take weeks, not the lack of a working model - see §3.1), and cost measurement per provider.
- **Test whether Salamandra's odd behavior is about this one model or about small, heavily multilingual-tuned models in general** - try a second model of the same kind, to see if the recurring-wrong-number pattern (§3.4) shows up again.
- **Full containerization.** Running everything in Docker containers, one container per agent (with Docker Compose), for easier deployment.
