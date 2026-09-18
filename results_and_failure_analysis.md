# Evaluation Results and Failure Analysis

## 1. Methodology recap

The system was tested four ways:

1. **Correctness** - the real specialized agents vs. two baselines, per category (Data Query, Analysis, Visualization), checked against ground truth (computed directly, never by an LLM - see below).
2. **Decomposition value** - the real agents vs. a *monolithic* agent with the exact same tools and prompts (copied in, not paraphrased) but as one agent, not split up. This separates "does splitting into agents help" from "does just having the tools help."
3. **Routing accuracy and end-to-end latency** - measured in one pass through the real orchestrator (router -> agent -> narrator), kept separate from the correctness runs, which force routing so each agent's own ability can be checked alone.
4. **Report Agent quality** - checked by hand, not scored: a session summary has no single right answer, so it's rated on accuracy, completeness, no-fabrication, and fluency. Five normal sessions plus one session with impossible questions (§4.2), to see if the agent makes something up.

**Only accuracy can be pulled down by a mistake that isn't the Report Agent's own fault.** If an earlier turn got a wrong answer (the agent's mistake, or a routing mistake) and the Report Agent just repeats it unchanged, that counts against **accuracy** - accuracy asks whether what the report says is correct, not just whether it matches what it was given. **No-fabrication** only looks at whether the Report Agent invented something nobody computed (repeating someone else's wrong answer isn't that); **completeness** and **fluency** don't depend on correctness either. So a report can score low on accuracy and high on the other three in the same session - see §5.7 and §8 for real examples.

All comparisons use structured output (rows, statistics results), never the narrated text, since the same correct answer can be worded many ways. The baseline uses a short, generic prompt, not the agents' tuned ones, to show the value of the whole architecture; the monolithic agent uses the *same* tuned prompts, copied in verbatim, to isolate the value of splitting the work up.

This wasn't the original plan for the monolithic agent - the first version used a short prompt I wrote myself, much shorter than the real agents' combined prompts (1,131 words today). If the monolithic agent had done worse with that version, I wouldn't have been able to tell whether that was really about the architecture (one agent vs. several) or just a less detailed prompt. I caught this before running the evaluation and fixed it by copying in the real prompts exactly as they are.

**How scoring works.** Data Query and Visualization answers are scored by comparing the returned rows against the ground-truth rows: order doesn't matter, count does (a duplicate row must appear the same number of times), and numbers are matched with a small tolerance (0.01). Analysis answers are scored by comparing the specific statistic returned (mean, `t_statistic`, regression r², ...) to the ground-truth value, also with a tolerance. The Report Agent is scored subjectively, by hand, since a summary has no single correct answer to check.

**Where the ground truth comes from.** It's produced by a script (`src/eval/ground_truth/`) that runs a hand-written reference SQL query or analysis plan against the real database - no LLM involved, so it's repeatable, but only as correct as those reference queries, which I wrote myself. The evaluation found and fixed bugs in two of them (`compute_ttest` §3.5, an earlier `compute_regression` target bug), so this is a real dependency, not a formality.

Two more real correctness bugs were caught and fixed before any evaluation ran, so there's no before/after evaluation data for them, but they're worth knowing about: the Analysis Agent's regression function used to pick its prediction target by its position in the column list, not by name - since the LLM naturally lists columns in question order ("predict profit from sales, discount, quantity" puts profit first), this could swap the target and give a low-r² wrong answer, with no error raised. And the Analysis Agent could originally only ever `SELECT` whole columns, with no `WHERE` clause at all, so a question with a condition in it (like "average profit in the West region") was computed over the *entire* table instead, again with no error. Both were fixed by adding an explicit field to the plan (`target`, `filters`) instead of relying on an implicit convention the LLM had no way of knowing about. Either bug would have corrupted results without any error to flag it, if I hadn't caught them first.

All three providers are called as plain text-completion models: one prompt in, one block of text out, no tool-use/function-calling API, no web search, no retrieval. This is about how the model is called, not whether real computation happens - it does, differently for each agent that touches the database:

- **Data Query**'s output is the SQL query itself, as plain text - the model writes it directly, and that exact text runs.
- **Visualization**'s output is a JSON object that includes a SQL query the model writes itself, same as Data Query - so unlike Analysis, it *does* write its own SQL. It also picks the chart type from a fixed list of 6, similar to how Analysis picks a statistic: the model decides *which*, not how to draw it.
- **Analysis**'s output is a JSON plan naming one of 15 pre-written functions (mean, correlation, regression, PCA, K-Means, ...) and its parameters; separate Python code (not the LLM) runs that function against the real data (see §6). Unlike the other two, it never writes any SQL - the columns and filters it names are turned into a query by other code.

So the model always decides *what* to do, but the actual computation never comes from code it wrote itself, and the only thing that varies between providers is the model's reasoning, not what tools it can reach.

Every LLM call uses `temperature=0` on every provider (`src/llm/factory.py`), keeping answers close to the same each time so re-running the benchmark gives similar results - not perfectly identical (a live API can still vary a little), but with most of the randomness removed.

The benchmark has 55 questions: 30 Data Query, 15 Analysis, 10 Visualization, split into easy/medium/hard. With so few per category, one flipped answer moves the percentage a lot: 3.3pp per question in Data Query, 6.7pp in Analysis, 10pp in Visualization. Keep this in mind throughout - a 10pp gap in Visualization can be one question.

**§2 and §3 are Anthropic `claude-haiku-4.5`, in English** - the first run done, before Spanish/Catalan existed, and the main reference dataset throughout. Two bugs found during the evaluation were fixed and the affected runs repeated (§3.2, §3.5 have the before/after). Two other things happened later: the same 55 questions were translated and run in Spanish and Catalan on this same model (§7), and two separate local models (Llama 3.1 8B, then Salamandra-7b-instruct - both run locally via Ollama) were each evaluated in all three languages (§5).

---

## 2. Primary results (Anthropic, Claude Haiku 4.5, English) — current, post-fix

### 2.1 Correctness

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% (28/30) | 76.7% (23/30) | 90.0% (27/30) | +16.7pp | +3.3pp |
| Analysis | 100% (15/15) | 40.0% (6/15) | 80.0% (12/15) | +60.0pp | +20.0pp |
| Visualization | 90.0% (9/10) | 50.0% (5/10) | 100% (10/10) | +40.0pp | -10.0pp |

"pp" means percentage points (e.g. 93.3% minus 76.7% is 16.7pp, not "16.7%") - used throughout wherever two percentages are compared directly.

The Analysis figures reflect two corrections made during the evaluation (before them: baseline 20.0%, monolithic 86.7%, architecture value +80.0pp): a bug in `compute_ttest` (§3.5) and a limitation in this evaluation's own scoring logic (§3.2), both with before/after evidence below.

### 2.2 Routing accuracy

**90.9% overall** (50/55). Per category: Data Query 100%, Visualization 100%, Analysis 66.7%. Unaffected by the fixes above (routing behavior didn't change, only how correctness is scored did).

This number is a floor, not the true error rate: it's measured against a fixed `expected_agent` label, but some questions two agents can both answer correctly. Checking the 5 misrouted questions by hand against the ground truth (§3.4), all 5 were answered correctly by the agent they were sent to - so by answer quality, routing here is effectively 100%. Automating this check is future work (§9).

### 2.3 Latency

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Category | Agent-only | Full pipeline | Baseline | Monolithic |
|---|---|---|---|---|
| Data Query | 1.117s | 3.500s | 1.078s | 1.127s |
| Analysis | 1.367s | 3.817s | 5.086s | 1.366s |
| Visualization | 1.710s | 4.940s | 1.628s | 1.640s |

The baseline's Analysis latency (5.086s) is much higher than every other cell. That matches §3.5: it now writes a more complex manual SQL query (per-group mean, count, min, max, and a standard deviation via subquery) instead of a short one.

The full pipeline is 3-4x the agent-only time because it makes three LLM calls (router, agent, narrator) instead of one - the price of the architecture. On a fast hosted model this is a few seconds; on a slow local model it multiplies (three calls of 15-40s each - see §5), so the overhead matters more for a local deployment. All numbers here are machine-dependent, measured on the setup in §5, not tuned hardware.

### 2.4 Retry / self-correction

Data Query, Analysis, and Visualization share a self-correcting loop (`src/core/retry.py`): the LLM produces a SQL string or JSON plan, it runs, and if it errors, the error is fed back to the LLM and it tries again, up to 3 attempts. "Retry rate" is the fraction of questions where this fired at least once.

**Retry rate: 0% in every category** (Anthropic English), unchanged by the fixes. The 55-question benchmark never triggered it; the session with impossible questions (§4.2) is the first time it fired, and it didn't recover. It first *succeeded* in the Anthropic Catalan run (§7.3), and fired a few more times in the local-model runs (§5).

---

## 3. Failure analysis

### 3.1 The "how many orders" problem

`COUNT(order_id)` gives 9,994 (every line-item row); `COUNT(DISTINCT order_id)` gives 5,009 (real order transactions, since one order can have several line items). Claude always picks the DISTINCT version whenever "orders" is counted - which even changes who "wins" on "which customer placed the most orders" ("Emily Phan" under DISTINCT vs. "William Brown" under the ground truth's convention). Not affected by the fixes below.

### 3.2 FIXED: a real limitation in the evaluation's own scoring, not in what the baseline can do

**Original finding**: the baseline scorer assumed a plain SQL model could only manage simple statistics like a mean; correlation, covariance, and t-test were marked `incorrect` automatically, regardless of what the baseline actually returned, on the assumption they can't be written as one SQL query. That assumption was wrong: Claude's baseline worked out the exact Pearson correlation formula by hand in SQL and matched the real system's value almost exactly, but was still marked wrong.

**Fix applied**: `check_baseline_analysis` now checks the key number for correlation, covariance, and t-test (e.g. comparing the specific `t_statistic` value against what the baseline returned), instead of auto-rejecting them. Regression, PCA, and K-Means are still auto-rejected, correctly - those need repeated steps or matrix math that one plain SQL `SELECT` can't do. That's a real limit of SQL, not an assumption in the scorer.

**Effect, confirmed by the re-run**: baseline Analysis correctness went from 20.0% to 40.0% - not because the baseline got better, but because it was always this capable and wasn't getting credit (its correlation answers on Q5 and Q13 now score correct, with no change to what it actually returns). The fix also still works in the other direction: on the t-test question, the baseline wrote an elaborate answer (mean, count, a hand-worked standard deviation for each group) but never computed a real t-statistic, and the fixed scorer still marks this one wrong, exactly as before.

**What the baseline can and can't do.** 3 of the 15 Analysis questions - regression (Q10), PCA (Q11), K-Means (Q12) - can't be done in a single SQL query at all: they need many repeated steps, or matrix math, and one `SELECT` can't loop or work through steps like that. This is a limit of the tool, not the model. The baseline is scored wrong on all 3 by design. This inflates the raw gap a little: the baseline's ceiling on Analysis is 12/15, not 15/15. On the 12 questions SQL *can* answer, the baseline scores 50% (6/12) and architecture value is +50pp, vs. 40% and +60pp over all 15 - both true, same conclusion either way. This only affects the baseline comparison; the monolithic agent has the same Python tools, so decomposition value (§2.1) is a clean comparison here.

### 3.3 The chart grouping problem

"Line chart of profit over time for the East region in 2017" never says how to group the dates. The real Visualization agent and the baseline both grouped by `order_date` (day by day) and were marked wrong against a ground truth grouped by month; the monolithic agent grouped by month and matched. This one question is the entire -10pp "decomposition value" in Visualization at n=10 - not a real capability gap, just a guess that happened to match.

### 3.4 Routing errors

All 5 routing misses (of 55, 90.9% accuracy) are the same pattern: an average/median question sent to Data Query instead of Analysis - "average discount," "median profit," "average profit, West region," "average sales, East/Furniture," "median sales, South region." Data Query and Visualization routing were both 100%.

**These 5 are not real errors - the Data Query agent answered all of them correctly.** A mean or median is just `AVG(...)` or a percentile query, answerable by either agent. Checked against the ground truth: 0.156 (avg discount), 8.67 (median profit), $33.85 (avg profit West), $346.57 (avg sales East/Furniture), $54.66 (median sales South) - all correct. So the router picking Data Query is a reasonable choice on an unclear question, not a failure. The 90.9% figure counts them as failures only because it compares against a fixed label.

This isn't always harmless, though: in the Llama run (§5) the router misroutes the *opposite* way, sending ranking questions to the Analysis agent, whose fixed menu can't group-and-rank - producing wrong answers stated with total confidence. Whether a misroute matters depends on direction and whether the receiving agent can actually do the task.

### 3.5 FIXED: `compute_ttest` now compares two groups, not two arbitrary columns

**Original finding**: `compute_ttest` ran a t-test between two numeric *columns* directly (e.g. discount vs. profit) - not what a t-test is for; a t-test compares one variable across two *groups*. This had a real effect: Report Agent Session 5 described the result as "a negative correlation," which a t-test doesn't even measure.

**Fix applied**: `AnalysisPlan` now has explicit `group_column` and `group_values` fields (exactly 2 values), `compute_ttest` splits the data into two real groups, and the benchmark question was rewritten to a real group-comparison question ("is there a significant difference in profit between the Consumer and Corporate segments?").

**Effect, confirmed by the re-run**: the real Analysis Agent and the monolithic agent both now give the correct result (`t_statistic=-0.856, p=0.392`, group means $25.84 Consumer vs. $30.46 Corporate), matching the ground truth exactly. The regenerated Session 5 confirms the fix worked end to end: it now correctly says the difference isn't statistically significant, replacing the old wrong claim.

### 3.6 Small formatting misses and the row-cap ordering issue

Minor, not worth fixing: `SELECT *` instead of the requested columns; pre-binned histograms as a different (not wrong) way to show the same thing; and the `MAX_ROWS` + `ORDER BY` interaction, where which rows come back depends on sort order once a result passes the 1,000-row cap.

---

## 4. Report Agent — qualitative results

### 4.1 Normal sessions 1–5 (Session 5 re-rated after the fix)

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Session | Accuracy | Completeness | No fabrication | Fluency |
|---|---|---|---|---|
| 1 — Data Query, easy | 3/5 | 5/5 | 2/5 | 5/5 |
| 2 — Analysis | 4/5 | 5/5 | 4/5 | 5/5 |
| 3 — Visualization | 5/5 | 5/5 | 5/5 | 5/5 |
| 4 — Mixed, realistic | 3/5 | 5/5 | 4/5 | 5/5 |
| 5 — Mixed, hard | **5/5** | 5/5 | **5/5** | 5/5 |
| **Mean** | **4.0/5** | **5.0/5** | **4.0/5** | **5.0/5** |

Session 5 went from 2/5 to 5/5 on both accuracy and no-fabrication - a direct result of the `compute_ttest` fix (§3.5), not a different reading of the same report. Mean accuracy and no-fabrication across all five sessions rose from 3.4/5 to 4.0/5 because of this one fix.

Sessions 1, 2, and 4 weren't touched by the fixes and keep their old ratings: Session 1 makes up a profit-margin number nobody asked for (no-fabrication 2/5); Session 4 has small arithmetic errors and mixes up which turn a number came from.

### 4.2 Session 6: behavior on impossible questions

This session checks something the other five can't: when an agent fails or is asked for something the data doesn't have, does the Report Agent say so, or invent a finding? All six questions can't be answered from the Superstore data. Rated with a failure-focused template instead of the normal one.

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Dimension | Score | Justification |
|---|---|---|
| No fabrication | **2/5** | The report claims Q6's chart "successfully" revealed a positive correlation - a finding no agent computed - and files the impossible request (asked as "employee salary vs profit") as a plain "sales vs profit" analysis, hiding the impossibility. It does *not* invent age or marketing-spend values, and its 2016 figures match the real query rows, so 2, not 1. |
| Failure transparency | **3/5** | Two of three failures (age, marketing spend) are listed with correct reasons. Q5 is handled well. But Q6's impossibility is hidden, and Q1 is described as a "system security restriction" rather than a missing column. |
| Completeness | **4/5** | All six questions are covered. Docked one point since Q6 is shown as something other than what was asked. |
| Fluency | **5/5** | Well structured. If anything, too confident - the made-up correlation reads just like the real findings. |

What each agent did with its turn:

| Q | Asked for | Routed to | What happened |
|---|---|---|---|
| 1 | Average customer age (no such column) | data_query | Errored with the wrong message (`UnsafeSQLError: Only SELECT queries are allowed`) instead of "no such column: age." 3 retries, all rejected. |
| 2 | Sales for customer "Jonathan Q. Fakename" (doesn't exist) | data_query | Correct - null result, narration says the customer may not exist. |
| 3 | Correlation of "marketing spend" with profit (no such column) | analysis | Planner used `sales` instead, then broke its own JSON with an extra note, failing with a `ValueError` after 3 retries. Would have called a sales-vs-profit correlation "marketing spend" if the JSON had been clean. |
| 4 | Orders shipped to Germany (data is US-only) | data_query | Correct - returns 0, though the narration doesn't mention the data is US-only. |
| 5 | "Why did profit decline in 2016?" (false premise) | data_query | Best handling of the six: pushed back ("I cannot confirm that profit declined overall in 2016"), gave real monthly numbers, said 2015 data would be needed. No made-up answer. |
| 6 | Scatter of "employee salary" vs profit (no such column) | viz | Chart engine actually plotted `Sales` vs `Profit` (saved file titled "Sales versus Profit per Order"), but the narration kept calling it "Employee Salary" and invented a salary range ($14.62-$957.58). Reported as a success. |

Things worth knowing:

- The main problem happens earlier in the pipeline: the Data Query and Analysis planners substitute `sales` for a missing column (Q3, Q6). The Report Agent mostly just repeats what it's given.
- The Report Agent is actually more grounded than the narration - for Q6 it used the real chart data (labelled Sales/Profit) and avoided the "employee salary" mistake, but still didn't say the request was impossible, and added an uncomputed "positive correlation" claim.
- The retry loop ran for the first time here (Q1, Q3, `attempts: 3`) but couldn't recover, because a missing column isn't a syntax error a retry can fix.
- For the clearest cases (age, marketing spend, missing customer) the report invents nothing. The risk is specifically when an agent half-answers with a substituted column and passes up a normal-looking result.

---

## 5. Other models (Llama, Salamandra), and why Groq was dropped

Anthropic is the primary dataset (§2). Two local models, both run through Ollama, were also run on the current system, in all three languages - Llama's real numbers are in §5.3-5.7, Salamandra's follow later in this section.

### 5.1 What happened with each

**Groq.** I tried to run the evaluation on Groq, but ran into real infrastructure problems that made it impractical to finish. The model I originally planned to use (`llama-3.3-70b-versatile`) was retired by Groq mid-project, so I switched to its closest replacement (`openai/gpt-oss-120b`). On the free tier, that replacement's daily token limit turned out to be far too tight for this evaluation: a single benchmark run, in a single language, used almost the entire 200,000-token daily allowance by itself. At that rate, finishing even an English-only run would mean waiting for the quota to reset and resuming several more times; matching the same three-language depth I have for Anthropic and Llama would realistically take 1.5-3 weeks of repeating that every day. I looked into paying for Groq usage, the same way I already do for Anthropic, to remove the daily limit - but Groq's paid tier signup is currently disabled ("temporarily unavailable due to high demand"), which also appears to be a wider, ongoing issue other users are reporting, not something specific to my account. Given this, I decided not to pursue a Groq run any further. No Groq numbers are reported anywhere in this document.

**Llama 3.1 8B (local, via Ollama).** The benchmark ran on the current system, for all three languages - real numbers in §5.3-5.7.

**What I did instead of Groq: a second, different local model.** My supervisor suggested trying another model to run locally through Ollama rather than pushing through Groq's free-tier limits or waiting for its paid tier to reopen, picked to be clearly different from `llama3.1:8b` - either a model built for these specific languages, or a much smaller one, to see what changes. I picked **Salamandra-7b-instruct** (Barcelona Supercomputing Center), for a specific reason, not just because it was suggested: it's almost the same size as `llama3.1:8b` (7.77B vs. 8B parameters), so switching to it isolates one thing - what the model was trained on - instead of also changing model size at the same time.

Here's why that specific difference matters. Meta's own Llama 3.1 model card lists 8 languages it was specifically fine-tuned and safety-tested for: English, German, French, Italian, Portuguese, Hindi, Spanish, Thai. Catalan isn't one of them. But the model card also says plainly that "Llama 3.1 has been trained on a broader collection of languages than the 8 supported languages" - so this isn't "the model doesn't know Catalan," it's "Catalan didn't get the same dedicated fine-tuning attention as those 8." That matches exactly what this evaluation already found: Llama clearly has real, working Catalan ability (§5.3, 70-100% correctness), just somewhat weaker than English or Spanish. Salamandra was built specifically to close gaps like this one: trained on 35 European languages, with Spanish, Catalan, Galician, and Basque oversampled 2x, by a public research center whose whole purpose is covering languages general models under-serve.

So Salamandra isn't a random third pick - it directly tests a question §8 could only leave open before: is Llama's language decline (English, then Spanish, then Catalan) really about how much training attention each language got, or was it just noise from one run? Same size class, opposite language-training design, real answer either way.

**A quick comparison of all three models, as models** (not as measured in this evaluation - that's the rest of this document):

| | Anthropic Claude Haiku 4.5 | Meta Llama 3.1 8B | BSC-LT Salamandra 7B Instruct |
|---|---|---|---|
| Parameters | Not published | 8B | 7.77B |
| Context window | 200,000 tokens | 128,000 tokens | 8,192 tokens |
| Released | Oct 2025 | Jul 2024 | 2024 |
| Hosting | Hosted API, paid | Local, free | Local, free |
| Languages | No fixed published list - broadly multilingual from scale and training data, nothing specific documented for Catalan | 8 languages officially fine-tuned and safety-tested (not including Catalan), trained on more than that | 35 European languages, with Spanish/Catalan/Galician/Basque oversampled 2x |
| License / cost | Proprietary, $1 / $5 per million tokens (in/out) | Free (Llama license) | Free (Apache 2.0) |

Why each one is in this evaluation: **Anthropic** is the upper-bound reference - a strong, fast, hosted model, to see what the architecture looks like on something clearly capable. **Llama 3.1 8B** is the general-purpose local baseline - small, free, and (per above) not specifically tuned for one of this project's two non-English languages. **Salamandra 7B** is the targeted counterpoint - same size as Llama, but built for exactly the languages Llama wasn't specially tuned for.

### 5.2 Provider trade-offs seen during development

- **Anthropic** - fast, reliable, no rate-limit trouble. Costs money per token (small here, but real).
- **Local models (Llama, Salamandra), via Ollama** - free and private, but slow on a normal laptop (CPU only): ~12-20s per question once warm, 160-340s to load the model the first time, several hours for a full run, CPU at 100% the whole time.

**What a "warm-up" call is, and why it only matters for Ollama.** Before timing real questions, the benchmark sends one throwaway question through the same code first, uncounted (`src/eval/utils/warmup.py`) - because Ollama has to load the whole model into memory the first time it's used, which takes 160-340 seconds on its own and has nothing to do with actually answering. Without a warm-up, that cost would land inside the first timed question and make it look far slower for no real reason.

I found this while testing Llama, before the full evaluation and before Salamandra was ever added to the project: with no warm-up at all, the first question in a run was taking much longer than the rest, which mattered since latency is one of the things this project measures. My first fix used a warm-up question unrelated to the real ones, and it didn't work - the first real question was still slow, as if nothing had warmed up. Only a warm-up that went through the *exact same code path* as the real questions (same function, same kind of prompt) actually fixed it. So a warm-up only pays the loading cost if it exercises the same path as what's about to be timed.

This only matters for Ollama, since it loads a model locally. Anthropic is a hosted API with nothing to load, and its numbers show no such pattern - the first question in a run isn't slower than the rest.

**A second real Ollama-only bug, found while re-running the Report Agent benchmark after the language fix (§5.7): nothing was limiting how many tokens one answer could generate.** `ChatOllama` was set up with no `num_predict` value, so Ollama used its own default instead - which turned out to be about 40,960 tokens, basically no limit at all. On one adversarial-session report, the model never produced a stop token, and the call kept running on CPU for over 5 hours before I killed it by hand. I checked it wasn't just frozen by asking the local server directly (`llama.cpp`'s `/slots` endpoint): it was still actively generating the whole time, just with nothing telling it when to stop. Fixed by setting a cap of `num_predict=2048` for Ollama in `src/llm/factory.py` (Ollama only - every real answer here, a SQL query, a JSON plan, a report, easily fits under that; Anthropic and Groq don't use this setting and aren't affected). I ran the same session again afterward and it finished normally in a few minutes.

The Llama run was done in stages, with breaks between them to keep the laptop from overheating during multi-hour runs.

### 5.3 Llama correctness, by language

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" = monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 83.3% | 43.3% | 80.0% | 76.7% | 36.7% | 80.0% | 70.0% | 26.7% | 60.0% |
| Analysis | 100% | 33.3% | 80.0% | 93.3% | 20.0% | 40.0% | 93.3% | 20.0% | 33.3% |
| Visualization | 100% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% |

The real system stays close to Anthropic even on this much smaller local model (70-100% vs. 90-100%), and does better on Visualization in all three languages. The baseline is much weaker on Data Query (27-43% vs. Anthropic's 77%): a small model writing raw SQL with no tools makes real mistakes, not just the counting problem from §5.5. Correctness drops a little from English to Spanish to Catalan, most visibly on Data Query (83 → 77 → 70%) and the monolithic agent (80 → 80 → 60%) - likely just normal noise from a small model, since the actual mistakes are the same kind in all three languages (§5.5).

### 5.4 Llama routing - the real weak point

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 56.4% | 50.9% | 52.7% |
| Data Query | 20% (6/30) | 20% (6/30) | 20% (6/30) |
| Analysis | 100% | 86.7% | 86.7% |
| Visualization | 100% | 90% | 100% |

**Data Query routing is stuck at exactly 20% in all three languages**, almost all misrouted to Analysis (24/24 in English; 23/24 in Spanish and Catalan, a few going elsewhere). This model can't reliably tell "retrieve/aggregate with SQL" apart from "compute a statistic" - the opposite of Anthropic's routing gap (§3.4).

**And this time it's not a harmless mix-up.** Checking what actually happened: of English's 24 misroutes, 9 errored outright, and only 2 of the remaining 15 landed on the right answer - e.g. correctly naming "Consumer" as the biggest segment, but giving an average instead of a total. The rest are just wrong, stated as if right (e.g. "the business performs best in the South region," when it's the West). Spanish and Catalan show the same pattern. The Analysis agent's fixed menu can't group-and-rank, so unlike Anthropic's misroutes, these are answers a real user would see and believe - not just a scoring technicality.

The misrouting also causes outright pipeline failures: 10/55 (EN), 8/55 (ES), 11/55 (CA), almost always because a Data Query question reached Analysis and it couldn't handle it (`no such column`, `No numeric columns found`, `Unknown analysis 'sum'` - the model making up an analysis type that isn't in the menu).

### 5.5 Llama failure analysis - mostly the same mistakes in all three languages

The Data Query agent repeats the same mistakes across all three languages - real weaknesses of the model, not translation artifacts:

- **"Revenue" confused with "profit"**: `SUM(profit)` written where the question asks for revenue - in all three languages ("who generated the most revenue", "product with the most revenue").
- **Min/max of one row instead of grouping first**: e.g. `MIN(profit)` or `MAX(quantity)` on the raw table instead of grouping by region/product first, then taking the min/max of the totals - for "least profitable region" and "product with the most units sold," all three languages.
- **Correct query, missing `LIMIT 1`**: returns every row instead of the top one - English and Catalan.
- **Wrong column for "how many customers/purchases"**: Spanish used `COUNT(*)` instead of `COUNT(DISTINCT customer_id)`; Catalan summed `quantity` instead of counting orders at all.

Catalan also has two mistakes not seen elsewhere:

- **Region confused with State.** Twice, a question naming "state" got grouped by `region` instead - two different location columns mixed up, not just a wrong aggregate.
- **Picking the wrong replacement analysis.** Asked to cluster orders into 3 groups, the model noticed "groupby" wasn't a valid option, then guessed an unrelated replacement ("describe," a simple summary) instead of the actual K-Means option - and broke its own JSON output explaining the swap. Happened on the same clustering question in both Session 5 and the standalone benchmark.

One possible language-sensitive slip: Spanish "¿cuál es el descuento **medio**?" (average) was planned as `median` - "medio" and "mediana" may have been confused. Catalan's impossible age question also reasoned that age could be "approximated by the average order date" - a real attempt at a workaround rather than a refusal, that then failed on an unrelated JSON formatting error.

The one Visualization miss per language is the familiar §3.3 grouping problem - all three languages (and Anthropic, §7.4) show different granularity guesses on the same chart question, which never says how to group the data. Spanish and Catalan both grouped by *year*, an even coarser guess than daily or monthly.

### 5.6 Llama latency

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 12.5 / 13.7 / 19.8 s | 9.3 / 13.1 / 19.7 s | 12.4 / 16.7 / 16.3 s |
| Full pipeline (DQ/An/Viz) | 54.9 / 65.8 / 129.3 s | 44.5 / 62.3 / 143.8 s | 71.9 / 46.6 / 71.5 s |
| Retry rate | DQ 3.3%, Viz 10% | DQ 6.7%, Viz 10% | Analysis 6.7% (failed) |

10-25x slower than Anthropic, expected for local CPU inference. A full run took several hours per language, mostly from this per-question slowness plus the model-loading warm-up cost (§5.2).

Catalan also had the most pipeline failures of the three languages (11/55, vs. 8/55 Spanish and 10/55 English). This doesn't affect correctness, only how many pipeline calls errored.

### 5.7 FIXED (same bug and fix as §7.5): Llama's Report Agent, re-run after the fix

Same bug as Anthropic's (§7.5 has the full story): the Report Agent's output was always in English no matter the session's language, on all three models tested, since the code had no language setting for it at all. This section shows what the same fix did to Llama's numbers (§5.12 has Salamandra's). One extra problem turned up while re-running this on Llama: the Spanish Session 6 re-run got stuck for over 5 hours generating a single response, before I killed it and found the real cause - nothing was limiting how many tokens Ollama could generate in one go (§5.2 has that story). Fixed at the same time as the language bug, then re-run cleanly.

Same 6 sessions and rubric as the Anthropic review (§4, §7.5).

**Model: Llama 3.1 8B (local, via Ollama). Languages: English (EN, unaffected by the language fix), Spanish (ES), Catalan (CA).**

| | EN sessions 1-5 mean | ES sessions 1-5 mean | CA sessions 1-5 mean |
|---|---|---|---|
| Accuracy / Completeness / No-fab / Fluency | 3.0 / 5.0 / 4.2 / 4.6 | 3.0 / 5.0 / 5.0 / 4.8 | 3.4 / 5.0 / 5.0 / 4.8 |

| Session 6 (impossible questions) | No-fab | Failure-transp. | Completeness | Fluency |
|---|---|---|---|---|
| EN | 1 | 2 | 4 | 4 |
| ES | 1 | 2 | 4 | 4 |
| CA | 2 | 2 | 5 | 4 |

Accuracy stays low in both languages, for the same reason as before this fix: Llama's weak routing (§5.4) sends several questions to an agent that can't really answer them, and the report just repeats a wrong or incomplete answer without adding anything made up of its own - that counts against accuracy, not against no-fabrication (§1 explains the difference). One new mistake turned up this time, and it's different from the rest: in Spanish Session 3, the chart turn itself correctly says Technology has the highest category sales ("la categoría de tecnología generó las ventas totales más altas") - but the Report Agent's own summary gets it wrong anyway, crediting Furniture instead. Unlike everything else in this section, that mistake is the Report Agent's own, not something it copied from a bad answer.

No-fabrication for sessions 1-5 is better than the old English numbers, in both new languages - the wrong-answer cases from §5.4's routing problems don't come with any extra made-up detail added on top this time. Session 6 tells a different story, and shows the worst problem found here isn't about report language at all: asked for the correlation between "marketing spend" and profit (a column that doesn't exist), the Analysis Agent quietly uses `discount` instead and reports a precise, confident correlation as if it were the real answer - `-0.219` in Spanish, `-0.22` in Catalan - in both new languages, exactly like before this fix. Every Anthropic run on this same question either failed with an error or refused to guess (§7.5). Spanish adds a second made-up claim on top: its report also says there is a "negative relationship" between the (made-up) "employee salary" and profit in the Q6 chart - but that chart doesn't show any such relationship either way, since it's really sales vs. profit. Catalan's report describes the same chart without making up a direction for the relationship.

### 5.8 Insightful findings

The Llama results are real data for all three languages, and so are Salamandra's (§5.9-5.12, added later for a specific reason - §5.1). Anthropic is treated as the main, most relevant model in this evaluation - the largest one tested, and the one the results show performing most solidly (§2, §7). Translations for all three languages, on all three models, are one pass done by me, not independently checked. The routing weakness (§5.4) and the marketing-spend fabrication (§5.7) are two findings on Llama with no equivalent on Anthropic - real differences in what the models can do, since everything else about the pipeline is identical. Salamandra adds a third, different set of weaknesses on top of those (§5.11), rather than repeating either one.

### 5.9 Salamandra correctness and routing, by language

**Model: Salamandra-7b-instruct (local, via Ollama). Languages: English (EN), Spanish (ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" = monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 63.3% | 43.3% | 26.7% | 53.3% | 36.7% | 20.0% | 56.7% | 36.7% | 26.7% |
| Analysis | 80.0% | 13.3% | 33.3% | 86.7% | 20.0% | 26.7% | 80.0% | 13.3% | 46.7% |
| Visualization | 50.0% | 50.0% | 70.0% | 50.0% | 40.0% | 60.0% | 40.0% | 50.0% | 60.0% |

The core claim of this whole project holds up even on this weaker model: on Data Query and Analysis, the real agent clearly beats the baseline in every language - the multi-agent design still adds value when the underlying model makes far more mistakes overall than Anthropic or Llama. Visualization breaks that pattern, but not in one consistent direction: the baseline ties the real agent in English, loses to it in Spanish, and beats it in Catalan - no reliable architecture value either way. The monolithic agent, though, beats both the real agent and the baseline in every language. Data Query and Analysis also show the monolithic agent doing *worse* than the agent alone in every language - the opposite of what Anthropic and Llama showed (§2.1, §5.3), where the monolithic agent stayed close to the specialized agent. Combining all three system prompts into one call appears to cost this particular model more than it costs the other two.

**Routing accuracy:**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 78.2% | 78.2% | 74.5% |
| Data Query | 70.0% | 96.7% | 96.7% |
| Analysis | 80.0% | 26.7% | 13.3% |
| Visualization | 100% | 100% | 100% |

Data Query routing gets *better* in Spanish and Catalan than in English (70% to 96.7%), while Analysis routing falls apart in those same two languages (80% down to 26.7%, then 13.3%). Checking exactly where those Analysis questions went: every single one was sent to Data Query instead (11/11 in Spanish, 13/13 in Catalan). This is close to a mirror image of Llama's weak point, which was Data Query stuck at 20% in every language while Analysis stayed strong (§5.4) - the two local models fail at routing in close to opposite directions.

### 5.10 Salamandra latency, and a hardware note

**Model: Salamandra-7b-instruct (local). Languages: English (EN), Spanish (ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 12.6 / 15.2 / 26.3 s | 9.9 / 15.2 / 23.0 s | 8.9 / 16.3 / 31.8 s |
| Full pipeline (DQ/An/Viz) | 31.0 / 85.1 / 155.1 s | 30.0 / 86.7 / 54.8 s | 40.6 / 102.5 / 77.0 s |
| Retry rate | DQ 0%, Viz 6.7% | DQ 0%, An 6.7%, Viz 6.7% | DQ 3.3%, An 6.7%, Viz 3.3% |

Slower than Llama across the board despite a close parameter count (7.77B vs. 8B), and Visualization's full-pipeline time swings a lot between languages (155s in English, 55s in Spanish, 77s in Catalan) - on this hardware, that is at least as much about the machine as about the model. The laptop used for every Ollama run has only 7.4GB of RAM and no GPU, and was measurably swapping memory to disk during these runs. One call during the Catalan correctness benchmark failed with `ResponseError: model runner has unexpectedly stopped` - a one-off crash, not a repeating pattern, and consistent with running a model this size on a machine this tight on memory rather than a problem with the model itself.

### 5.11 Salamandra's Report Agent: a number that would not go away

Reading the actual reports (not just checking their language) turned up something more specific than "the model makes mistakes": the same wrong numbers show up for different questions, in different sessions, in all three languages.

**`108,418.4489`.** This exact figure appears as the answer to "What is the total profit?" (Session 1, all three languages - the correct value, used everywhere else in this document, is $286,397.02) *and* as the answer to "What is the average profit in the West region?" (Session 2, all three languages - the correct value is $33.85). Two different questions, three languages, one number, and it matches neither correct answer. This didn't come from the Report Agent - it is already in the underlying Data Query turn - but it shows up unchanged across every language this evaluation tested, which points to a problem in how this model generates SQL for these two questions, not a translation issue.

**`42.5` years old.** Session 6 asks "What is the average age of our customers?" - a question this system cannot answer at all, since there is no age column (every other model either refuses or returns a clearly broken number tied to order dates, e.g. Anthropic's "9.84 years," §7.5). Salamandra's own turn gives three different numbers across the three languages (35 in English, 34.67 in Spanish, 30 in Catalan) - but the *Report Agent*, writing the final summary, states "42.5 years" in all three languages regardless of what its own turn said. That is not a rounding difference or a translation slip: it is the same specific, wrong, made-up number appearing three separate times, replacing three different real inputs.

A related pattern shows up more than once: a real number from one turn gets reused as the answer to an unrelated question. Session 6 asks for the total sales of a customer who does not exist ("Jonathan Q. Fakename") - the correct behavior, seen from other models, is to report no data found. Salamandra's own turn does this correctly in Spanish ("not available in the data provided"), but the Report Agent's Spanish and Catalan summaries both state the answer as `725457.8245` or `725457,8245` - the exact total sales figure for the West region, used earlier in the same session for a completely different question, presented now as a specific customer's sales total.

These three examples (and others like them in the full session data) point to something more specific than "the report sometimes gets facts wrong": in several cases, the model appears to reuse a plausible-sounding number it has produced elsewhere, rather than either computing the right one or admitting it does not have one. This matters beyond Salamandra specifically, since the same failure mode - reusing an unrelated real number as if it answers a different question - was not seen on Anthropic or Llama.

The other finding worth naming directly: **whenever the underlying turn honestly says it does not know something, the Report Agent's summary is the part most likely to replace that honesty with a confident, invented answer.** In the Session 6 examples above, the turns say "not available," "not clear," or fail outright with a real error - and the report each time supplies a specific number anyway. The reverse also happens at least once: Session 3 in English has three visualization turns that either fail outright or return no usable content, and the report still describes specific chart findings ("the Furniture category had the highest total sales," "sales were relatively stable... with a slight increase in the second quarter") that were never computed. Session 3 in Spanish, facing the same kind of failed turns, instead produces a completely empty report (just the four section headers, no content) - the opposite failure, but still not a useful report.

**On top of the number problem, the language fix (§7.5) does not hold as well here as it did for Anthropic and Llama 3.1 8B.** Two of the six Catalan sessions come back as complete reports written entirely in English, despite the language-matching instruction being sent exactly as it was for the other two models. Where the report is in the right language, section headers are often left half-translated or not translated at all ("Preguntas Asked," mixing an English word into a Spanish sentence) - something that did not happen with either of the other two models tested.

### 5.12 Salamandra Report Agent - ratings

Same 6 sessions and rubric as the Anthropic and Llama reviews (§4, §7.5, §5.7).

**Model: Salamandra-7b-instruct (local). Languages: English (EN), Spanish (ES), Catalan (CA).**

| | EN sessions 1-5 mean | ES sessions 1-5 mean | CA sessions 1-5 mean |
|---|---|---|---|
| Accuracy / Completeness / No-fabrication / Fluency | 2.2 / 4.0 / 3.8 / 4.2 | 2.6 / 3.6 / 4.2 / 3.0 | 2.8 / 4.6 / 3.6 / 4.6 |

| Session 6 (impossible questions) | No-fab | Failure-transp. | Completeness | Fluency |
|---|---|---|---|---|
| EN | 1 | 2 | 4 | 4 |
| ES | 1 | 1 | 5 | 4 |
| CA | 1 | 1 | 5 | 4 |

Accuracy is the lowest of any model tested, in every language, for two different reasons: some answers are wrong because the underlying SQL or analysis step is wrong (the same kind of mistake seen on Llama), and some are wrong because the Report Agent changes a number that its own input turn already got right, for no clear reason (§5.11's Session 4 example, where the turn names the wrong top-profit category and the report substitutes the correct one anyway - not a fix, just a different guess that happened to land right). No-fabrication is the weakest score of any model on Session 6 specifically, for the reason detailed in §5.11: this is the model most likely to turn an honest "I don't know" into a confident, wrong answer.

---

## 6. What this evaluation does and does not establish

**Established, with evidence:**
- The specialized multi-agent architecture beats a minimal no-tools baseline, clearly, across all three categories (Anthropic Haiku, the reported dataset).
- It also beats a monolithic agent with the same tools and prompts (decomposition value: Data Query +3.3pp, Analysis +20.0pp, Visualization -10.0pp - the last one is entirely one unclear question, §3.3). This compares the monolithic agent against **individual agents in isolation** (routing forced correct), so a fairer end-to-end comparison (routing errors included) is future work (§9).
- **A real correctness bug and a real evaluation scoring limitation were found, fixed, and independently verified at three levels** (unit test, integration test, regenerated report) - a real example of the evaluation process catching and fixing real problems, not just producing a number.
- Routing errors are concentrated at the Data Query/Analysis overlap (simple aggregates), not random.
- **The architecture beats the baseline on two much weaker models too** (Llama, all three languages, §5.3; Salamandra, all three languages, §5.9): Llama's real-system correctness stays within 10-20pp of Anthropic's in English and Spanish, while the baseline is much worse everywhere. But routing quality doesn't transfer - Llama misroutes ~80% of Data Query questions (§5.4), and unlike Anthropic's routing gaps, these produce actually wrong answers.

**Scope / design choices (deliberate):**
- **Closed-world, and no LLM-written code.** No internet access, no agent writes or runs its own code - full detail in `docs/architecture.md`. Two consequences here: questions needing outside context ("why did sales drop in 2017", "is a 12% margin good," industry benchmarks) are out of scope, and the Analysis Agent can only answer what its 15 pre-written functions cover (§3.2 covers what that means for the baseline comparison).

**Not established, open questions:**
- **The baseline can't do 3 of 15 Analysis questions at all** (regression, PCA, K-Means, §3.2), scored wrong by design. Architecture value is +60pp over all 15, +50pp over the 12 SQL can express; the headline number uses all 15.
- Retry/self-correction effectiveness on Anthropic specifically: the 55-question English benchmark never triggered it, so the only two data points are the impossible-questions session (§4.2, fired but couldn't recover from a missing column) and the Catalan run (§7.3, the first and only successful recovery). Llama and Salamandra fire it far more often (§5.6, §5.10) and give a clearer picture overall (§8, "On retries"), but neither is Anthropic - so how well retry works *on a strong hosted model specifically* is still based on very little data.
- Whether decomposition value would hold at a larger question count.
- **Latency wasn't a focus.** The architecture costs three LLM calls instead of one (§2.3) - a few seconds on a hosted model, much more locally, plus a one-off model-loading cost the first time. All figures are from one modest laptop, not tuned hardware.
- **Cross-provider results.** Anthropic is the primary, complete dataset - the largest model tested, performing most solidly. Llama and Salamandra both have real results for all three languages (§5.3-5.7, §5.9-5.12). Cost per provider wasn't measured.
- **The scoring itself has two known simplifications** (`src/eval/checks.py`): numbers are compared with a fixed 2-decimal tolerance, not true floating-point precision - fine for this dataset's currency and count values, but would need adjusting for a dataset with much smaller or bigger numbers. And row comparison checks numbers and text as unordered sets, so it can't tell two different numeric columns apart if they happen to hold the same values in the same shape - not an issue for this benchmark's questions, but a trickier question set would need a check that understands what each column actually means.

---

## 7. Multilingual evaluation (Spanish and Catalan)

The 55 questions and 6 Report-Agent sessions were translated and run again, to see if language changes anything. This section is Anthropic only - Llama and Salamandra have their own three-language results in §5 (§5.3-5.7, §5.9-5.12).

### 7.1 Method

- Translations live in the dataset files: `question` is now a `{en, es, ca}` dict, so there is still one reference SQL and one ground truth per question.
- Ground truth doesn't change with language - scoring compares rows and numbers, not text.
- Value names stay in English in all languages (`West`, `Technology`, `Consumer`, `Second Class`), so the test is about the question's language, not translating stored values.
- System prompts stay in English - this tests the system as built, not a version tuned per language.
- Output is in `results/eval/anthropic/{en,es,ca}/`.

### 7.2 Correctness by language

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish (ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| **Real system** — Data Query | 93.3% | 93.3% | 100% |
| **Real system** — Analysis | 100% | 100% | 100% |
| **Real system** — Visualization | 90.0% | 90.0% | 90.0% |
| **Baseline** — Data Query | 76.7% | 73.3% | 76.7% |
| **Baseline** — Analysis | 40.0% | 40.0% | 40.0% |
| **Baseline** — Visualization | 50.0% | 60.0% | 60.0% |
| **Monolithic** — Data Query | 90.0% | 86.7% | 93.3% |
| **Monolithic** — Analysis | 80.0% | 93.3% | 86.7% |
| **Monolithic** — Visualization | 100% | 90.0% | 90.0% |

The real system does about the same everywhere (90-100%). The small changes are caused by the two known ambiguities in §7.4, not by the model being worse in a given language. The baseline fails on the same questions in every language.

### 7.3 Routing, latency, retry by language

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish (ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Routing accuracy — overall | 90.9% | 92.7% | 90.9% |
| Routing accuracy — Data Query | 100% | 100% | 96.7% |
| Routing accuracy — Analysis | 66.7% | 73.3% | 73.3% |
| Routing accuracy — Visualization | 100% | 100% | 100% |
| Agent-only latency — DQ / An / Viz (s) | 1.12 / 1.37 / 1.71 | 1.05 / 1.17 / 1.71 | 1.02 / 1.33 / 1.71 |
| Full-pipeline latency — DQ / An / Viz (s) | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 |
| Retry rate | 0% | 0% | 6.7% (Analysis) |

Routing works about the same everywhere - the same average/median misroutes as §3.4 (4-5 per language). Catalan has one extra: "Quin client va fer més comandes?" ("which customer made the most orders") went to Analysis.

The first time the retry loop actually recovered in the whole project was here: in Catalan Analysis, question 1's plan came back as invalid JSON, the loop retried, and the second try was correct (`attempts: 2`, `correct: true`). Latency differences between languages are small.

### 7.4 Are the wrong answers real errors? (all three languages)

Every wrong answer, in every language, is one of two already-documented ambiguities - not the model misunderstanding Spanish or Catalan:

- **Order-counting (§3.1).** `COUNT(DISTINCT order_id)` vs. `COUNT(*)` - which one the agent picks (and thus whether it's marked wrong) shifts between languages and questions, but it's a scoring mismatch on an unclear question, not a real mistake.
- **Chart grouping (§3.3).** Daily vs. monthly for the same under-specified chart - English missed it, Spanish and Catalan picked monthly and passed.

Set those two aside, and the real system is basically 100% correct in all three languages.

The baseline fails on the same questions everywhere, for good reason: SQLite has no `MEDIAN`/`STDEV`/`VAR_POP`, and regression/PCA/K-Means can't be done in one `SELECT`. The monolithic agent's few extra misses are the same vague questions ("where does the business perform best," "which segment dominates sales"), plus one Catalan-only JSON parse error.

### 7.5 FIXED: the Report Agent always answered in English, no matter the conversation's language

**Original finding.** Everything else in the system followed the conversation's language correctly - questions, per-turn answers, even number formatting ("725.457,82", "-0,219", "9,82 anys"). Only the Report Agent's output, and its "Questions Asked" section, stayed in English every time, even in a Spanish or Catalan session.

**Why this happened.** `generate_report_core(history)` had no language setting at all, and its instructions to the model ("Write a professional report...") are plain English with no mention of language anywhere. The per-turn narrator (`narrate.py`) doesn't have this problem, even though it also has no language setting: it puts the real question text straight into its own prompt ("User question:\n\n{question}"), so the model just naturally answers in the same language as the question. The Report Agent's prompt instead dumps the whole conversation as one block of JSON data - the original-language questions are in there, but buried under English instructions, and the English wins out.

**The fix.** The instructions stay in English, as they should. I added one extra line, built by a new `build_system_prompt(language)` function in `src/agents/report/prompts.py`. When the caller knows the language for sure - the eval scripts always do - that line names it directly ("Write the report in Spanish."). When it doesn't - a real conversation through the REPL, which has no language setting at all - the line instead says "write the report in the same language as the user's questions below." This second case is the one that actually matters for real use: a user who doesn't speak English just types in their own language, with nothing to configure, and needs the report back in that same language. I checked this directly, with no eval script involved at all: I called the Report Agent with a Catalan question and no language given, and it correctly wrote the report in Catalan, from that fallback line alone.

**Checked, then re-run.** I added two new unit tests, one for each of the two cases above. The Spanish and Catalan Report Agent benchmarks (all 6 sessions each) were then re-run on Anthropic with the fix in place, and the results below replace the old English-only ones completely. There's no useful "before" to keep here, unlike the t-test fix (§3.5) - grading an English report for a Spanish or Catalan session was never measuring anything real to begin with.

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN, unaffected by this fix), Spanish (ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| Sessions 1–5 mean — Accuracy / Completeness / No-fabrication / Fluency | 4.0 / 5.0 / 3.8 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 |
| Session 6 (impossible questions) — No-fab / Failure-transparency / Completeness / Fluency | 2 / 3 / 4 / 5 | 4 / 3 / 5 / 5 | 4 / 3 / 5 / 5 |

Sessions 1-5 score a little higher in both new languages than in English. The main reason: the fake profit-margin number that shows up in English Session 1 (§4.1) doesn't appear in either the Spanish or Catalan version, and nothing else got invented in its place. There is one real mistake in both: Session 4's segment breakdown (Consumer/Corporate/Home Office) has the right order counts in both languages, but the percentages worked out from them are wrong, in two different ways - Spanish's three percentages add up to 110%, Catalan's add up to 91.7%. Just a plain arithmetic mistake by the model each time, not a data problem.

Session 6 also does better than English, but for a reason that has nothing to do with this fix: the per-turn narration for question 6 was already better in Spanish and Catalan before this fix, in the old evaluation too. The English chart turn invents a fake "employee salary" label and a made-up correlation; the Spanish and Catalan narration correctly describes it as a sales-vs-profit chart instead. That difference lives in the turns, not the report, so it shows up the same way now that the report is finally written in the right language. Failure-transparency stays at 3/5 in every language, for the same reason each time: question 1's answer ("9.84 years", really the average *order* age, not customer age - an odd result the narration itself already flags, and unrelated to this fix) gets turned by the report into a finding about how old the data is, instead of being stated plainly as something the system can't answer. Question 3's marketing-spend correlation is the only one of the three impossible questions each report handles honestly, by saying it failed.

### 7.6 What this part shows

- The system handles Spanish and Catalan about as well as English - correctness, routing, and latency all close to English, and every wrong answer traces to one of the two already-known ambiguities, not language misunderstanding.
- The one real gap found here - the Report Agent always writing in English regardless of conversation language - was fixed after this evaluation and independently re-verified (§7.5); the numbers above already reflect the fix, not the original bug.
- This was one model, one set of translations, done by me and not independently checked.

---

## 8. Overall conclusions

The benchmarks tag each question easy/medium/hard, and correctness by that tag was already in the raw output (`summary.csv`) but never pulled together. Doing that, alongside the language and model comparisons above, surfaces a few findings not visible in any single table.

**By difficulty.** Real-system vs. baseline correctness, averaged across the three languages, for Anthropic and Llama - the two models this breakdown was done for (Salamandra was added later, specifically to test the language question below, and wasn't run back through this particular cut of the data):

| | Easy: real / base | Medium: real / base | Hard: real / base |
|---|---|---|---|
| Anthropic - Data Query | 90.0% / 73.3% | 96.7% / 80.0% | 100% / 76.7% |
| Anthropic - Analysis | 100% / 33.3% | 100% / 66.7% | 100% / 16.7% |
| Anthropic - Visualization | 77.8% / 66.7% | 100% / 75.0% | 88.9% / 22.2% |
| Llama - Data Query | 90.0% / 60.0% | 73.3% / 30.0% | 66.7% / 16.7% |
| Llama - Analysis | 88.9% / 44.4% | 100% / 38.9% | 94.4% / 0% |
| Llama - Visualization | 100% / 100% | 100% / 75.0% | 77.8% / 33.3% |

- **The baseline loses the most ground on hard questions, in both models** - exactly where the architecture earns its keep the most. Anthropic's baseline drops to 16.7-22.2% on hard Analysis/Visualization while the real system stays at 88.9-100%; same shape on Llama, lower floor (0-33.3% baseline).
- **But the Analysis "hard" collapse is mostly about labeling, not pure difficulty** - the hard-tier questions are exactly the ones needing regression, PCA, or K-Means, which SQL can't express regardless of how conceptually hard they are. Data Query and Visualization hard questions are a fairer difficulty test (the baseline *can* attempt them in SQL), and there it still drops (Anthropic roughly flat, 73.3% to 76.7%; Llama 60% to 16.7%, a real decline).
- **Anthropic's real system is barely affected by difficulty; Llama's is.** Anthropic stays at 88.9-100% at every tier (the one dip, Visualization easy at 77.8%, is the §3.1 order-counting ambiguity, not a real effect). Llama visibly drops from easy to hard on Data Query (90.0% to 66.7%) and Visualization (100% to 77.8%) - a real capability gap for a smaller model, matching the mistakes clustering on harder questions in §5.5.

**By language.** The point of testing three languages was to see if language matters at all - and there was a real reason to expect it might not be a fair fight: English dominates LLM training text, Spanish has less, Catalan is a minority language with much less available anywhere, so a decline in that order (English, then Spanish, then Catalan) was plausible.

Anthropic is flat across all three (§7.2, §7.3) - correctness, routing, and latency stay within a few points of each other, and every wrong answer traces to the two already-documented scoring ambiguities, not language struggle. So the expected decline doesn't show up on a strong hosted model - it seems to know each language well enough for this closed-world task. Llama does decline in that order on Data Query and the monolithic baseline (§5.3), and its worst fabrications happened on the Catalan run (§5.7) - matching the expected pattern, for what that's worth. But Catalan also had the highest pipeline failure count of the three (§5.6), so some, but probably not all, of that decline may be hardware rather than language. Salamandra, picked specifically to test whether that decline was about language training (§5.1), points the other way instead - see the dedicated conclusion on this near the end of this section.

**By model.** The one finding that holds everywhere - every language, every difficulty tier, all three models: **the specialized multi-agent architecture beats a plain single-prompt baseline**, even on the two much smaller, free, local models, both clearly weaker than the hosted one in other ways, and clearly weaker than each other in different categories (§5.9, §5.3).

**By architecture design (does splitting the work up help on its own?).** This is different from "beats a plain baseline" - it's real system vs. the monolithic agent, same tools and prompts, one agent instead of several (decomposition value, §1). Real system minus monolithic, in percentage points:

| | Data Query EN/ES/CA | Analysis EN/ES/CA | Visualization EN/ES/CA |
|---|---|---|---|
| Anthropic | +3.3 / +6.7 / +6.7 | +20.0 / +6.7 / +13.3 | -10.0 / 0 / 0 |
| Llama | +3.3 / -3.3 / +10.0 | +20.0 / +53.3 / +60.0 | +10.0 / 0 / 0 |

Splitting the work up helps almost everywhere, but far more on Llama's Analysis (+20pp in English, growing to +60pp in Catalan) than on Anthropic (modest, 0 to +20pp) - splitting the "which statistic do I compute" decision out into its own agent matters much more for a small model, which has less room to juggle several tool sets in one prompt. The two negative numbers (Anthropic Visualization English, from the §3.3 chart-grouping question; Llama Spanish Data Query, -3.3pp) are single questions flipping at small n, not real reversals. Salamandra shows the same idea taken further (§5.9): its Data Query and Analysis decomposition values are consistently large and positive in every language, while Visualization's goes negative every time - the split helps most on exactly the categories where this particular model struggles most on its own.

**By routing.** Overall: Anthropic 90.9-92.7% across languages, Llama 56.4% (EN), 50.9% (ES), 52.7% (CA), Salamandra 78.2% (EN), 78.2% (ES), 74.5% (CA) - and each of the three models fails in a different place:

| | Anthropic EN/ES/CA | Llama EN/ES/CA | Salamandra EN/ES/CA |
|---|---|---|---|
| Data Query | 100 / 100 / 96.7% | 20 / 20 / 20% | 70.0 / 96.7 / 96.7% |
| Analysis | 66.7 / 73.3 / 73.3% | 100 / 86.7 / 86.7% | 80.0 / 26.7 / 13.3% |
| Visualization | 100 / 100 / 100% | 100 / 90 / 100% | 100 / 100 / 100% |

Anthropic's weak spot (Analysis) barely matters - every misrouted question still got answered correctly by whichever agent got it (§2.2, §3.4). Llama's weak spot (Data Query, stuck at exactly 20% in every language) is not harmless - most misrouted questions come back wrong, stated as if correct (§5.4). Same *kind* of mistake (mixing up two similar categories), very different consequences. Salamandra's weak spot is Analysis, and it gets worse outside English (80% down to 13.3% in Catalan) rather than staying constant like Llama's Data Query problem - every one of those misroutes lands on Data Query instead (§5.9).

**By latency.** Full-pipeline average (DQ/An/Viz), seconds:

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 |
| Llama | 54.9 / 65.8 / 129.3 | 44.5 / 62.3 / 143.8 | 71.9 / 46.6 / 71.5 |
| Salamandra | 31.0 / 85.1 / 155.1 | 30.0 / 86.7 / 54.8 | 40.6 / 102.5 / 77.0 |

Both local models are roughly 10-40x slower than Anthropic, expected for CPU-only inference instead of calling a hosted API. Language barely changes Anthropic's latency; both local models' numbers move around more between languages (e.g. Salamandra's Visualization time nearly triples from Spanish to English) - on this machine, that looks more like ordinary variation in the laptop's own state than a real language effect (§5.10).

**On retries.** Fires far more often on both local models (3.3-10% in at least one category per language for Llama, similar for Salamandra, §5.10) than on Anthropic (once, ever, in the entire evaluation, and it fixed itself) - a smaller model produces more broken SQL/JSON to begin with. It's also less reliable once triggered: some Llama retries fix the problem (English Visualization, 100% success), some don't (the K-Means/"describe" mix-up in §5.5 survived a retry and still failed). Real help on the weaker models, but not a substitute for actually understanding the question.

**On honesty (Report Agent).** Same rubric, all three models, normal sessions 1-5:

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 4.0 / 5.0 / 3.8 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 | 4.8 / 5.0 / 5.0 / 5.0 |
| Llama | 3.0 / 5.0 / 4.2 / 4.6 | 3.0 / 5.0 / 5.0 / 4.8 | 3.4 / 5.0 / 5.0 / 4.8 |
| Salamandra | 2.2 / 4.0 / 3.8 / 4.2 | 2.6 / 3.6 / 4.2 / 3.0 | 2.8 / 4.6 / 3.6 / 4.6 |

Surprising: Llama's no-fabrication score on normal sessions isn't worse than Anthropic's, sometimes a touch better - the accuracy gap is a routing problem, not an honesty problem: several Llama sessions ask the Analysis agent something it simply can't do (§5.4), and the report faithfully relays that wrong answer without inventing anything. The picture flips on the session with impossible questions, where every question truly can't be answered: Llama's no-fabrication score (1-2 across languages) drops below Anthropic's (2-3), with a confident, precise, invented correlation number in all three languages (§5.7), a complete answer made up for a turn that had actually failed, and sample rows mislabeled as computed statistics (§5.7, Catalan). Salamandra's Session 6 no-fabrication score is just as low, or lower, in every language (§5.12) - and worse in one specific way neither Anthropic nor Llama showed: the same wrong number standing in for different real answers across all three languages (§5.11). So a model can look equally honest on ordinary questions and still be much more willing to make something up the moment there is really nothing true to say - and which specific way it does that varies by model.

**Does training a model on Spanish and Catalan close the language gap seen on Llama?** This was the actual reason Salamandra was added (§5.1) - Llama's small decline from English to Spanish to Catalan (§8, "By language" above) could not be told apart from ordinary run-to-run noise, and Salamandra, at almost the same parameter count but trained with Spanish and Catalan specifically emphasized, was picked to test that directly. The answer this evaluation found is clear, and it is not the one that framing predicted: Salamandra does not perform more consistently, or more honestly, in Spanish and Catalan than in English - if anything the opposite. Its worst behavior, found and detailed in §5.11 - a fixed wrong age ("42.5 years") replacing three different real answers, a real number from one question reused as the answer to an unrelated one, complete reports written in the wrong language despite an explicit instruction to match it - all of this happened in the Spanish and Catalan sessions, not the English ones. So the comparison this evaluation set out to make gives a real answer: for this task, language-specific training data did not translate into more reliable behavior in that language, at least not for this model at this size. What actually seems to matter more, based on comparing all three models, is how reliably a model follows instructions and stays grounded in what it was actually given - a property that has little to do with which languages it was trained on.

**Bottom line.** The architecture's core promise - specialized agents with real tools beat one generic prompt - holds up everywhere this was tested: three languages, three different models. Splitting that same toolset across separate agents helps too, and it helps the weaker models more than the stronger one. What changes between models is everything that follows from those two points: which category the router gets wrong (and how much it costs when it does), how often self-correction is needed, how fast the answer comes back, and how the system behaves when a question truly cannot be answered. A smaller, free, local model is a real option for the core task, but both local models tested here need a better router and much closer supervision of their Report Agent before either could be trusted the way the hosted model was here - and, per the paragraph above, picking a model trained specifically on the target language is not a reliable shortcut to that trust.

---

## 9. Future work

This is the one place in the repo for ideas on what to build or change next. What the system can't currently do is listed separately, in `docs/architecture.md` (Current Limitations) - this section is about fixing or extending those, not restating them.

- **Make the agents actually cooperate.** Right now each agent is independent - the router picks one, it runs, done. They could pass results to each other directly (e.g. Analysis using a Data Query result as input), instead of only ever going through the orchestrator, or a planner could chain several agents for one question.
- **Remember recent turns, not just the current question.** Routing and narration only ever see the current question right now. Using the last few turns (not the whole history) would let the system understand something like "that region," referring back to an earlier answer.
- **More agents, or a wider Analysis Agent.** Add agent types (forecasting, data quality checks, ...), or widen the Analysis Agent's fixed list of 15 functions - for example ANOVA, so it can compare more than the two groups the current t-test is limited to, or paired samples.
- **A real code-generating agent.** A different kind of change from the one above - not more pre-written functions, but letting an agent write and run its own Python code, with no fixed list at all. No agent does this on purpose right now (§6): it trades flexibility for safety, a result that's always the same, and answers that can be checked against an exact right answer. This would also close the gap in §3.2 - the single-agent baseline can't answer 3 of the 15 Analysis questions because of the "SQL only, no code" restriction, not because of the number of agents involved; a single agent that could write real Python (e.g. with scikit-learn) wouldn't have that problem. Doing this safely would need real sandboxing (running the generated code somewhere isolated, with no access outside that one task) and a way to still check its answers, since a code-generating agent can't be checked against ground truth as directly as a fixed list of functions can.
- **Score the pipeline answers automatically.** The pipeline benchmark only records routing and latency, not whether the final answer was right. The misrouted questions were checked by hand here (§3.4), but automating it would give a real "routing quality by answer" number, and a fair end-to-end comparison of the monolithic agent vs. the full system as a user hits it (routing mistakes included) instead of vs. the agents with routing forced correct (§2.1).
- **Reduce the Data Query/Analysis routing overlap.** Right now a mean, median, or other simple statistic can be answered correctly by either agent (§2.2, §3.4), so there's no single right routing choice for those questions. Either the two agents' jobs could be split more clearly (e.g. Analysis only handles anything beyond a raw count or sum), or the benchmark's "expected agent" label could allow more than one correct agent per question.
- **Rewrite the benchmark questions that turned out to have more than one fair answer.** Different from the routing overlap above - this is about the question itself not having one single correct answer, no matter who answers it: "how many orders" (§3.1) can mean `COUNT(*)` or `COUNT(DISTINCT order_id)`, both reasonable; the "profit over time" chart (§3.3) never says whether to group by day or month. Either reword these questions to remove the ambiguity, or accept more than one correct reading in the ground truth, so a wrong score reflects a real mistake.
- **A second, harder dataset.** Everything here is on Superstore. A larger or messier dataset - or one with more than one table (e.g. Olist), to test JOIN handling - would show how much of what was found is specific to this one.
- **A general safety net on LLM calls, not just Ollama's token cap.** §5.2's runaway-generation bug was fixed by capping Ollama's output length, but nothing currently protects against a similar failure mode on another provider (e.g. a hung connection) - a wall-clock timeout on any LLM call, not just a token limit, would be a more general fix.
- **Finish the cross-provider picture** - a real Groq run, if its paid tier ever reopens (the free tier's daily token limit makes a full run take weeks, not the lack of a working model - see §5.1), and cost measurement per provider.
- **Full containerization.** Running everything in Docker containers, one container per agent (with Docker Compose), for easier deployment.
