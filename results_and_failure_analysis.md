# Evaluation Results and Failure Analysis

## 1. Methodology recap

The system was tested in four different ways, each answering a different
question:

1. **Correctness** - the real specialized agents vs. two baselines, per
   category (Data Query, Analysis, Visualization), checked against
   ground truth (computed directly, never by an LLM - see below).
2. **Decomposition value** - the real agents vs. a *monolithic* agent
   that has the exact same tools and the exact same prompts (the three
   agents' real prompts, copied in, not paraphrased) but is just one
   agent, not split up. This checks whether splitting the work across
   several agents helps, separately from just having the tools at all.
3. **Routing accuracy and end-to-end latency** - measured in one pass
   through the real orchestrator (router -> agent -> narrator). This is
   kept separate from the correctness runs, which force the routing so
   each agent's own ability can be checked on its own.
4. **Report Agent quality** - checked by hand, not scored: a session
   summary has no single right answer, so it's rated on accuracy,
   completeness, fabrication and fluency. Five normal sessions plus one
   session with impossible questions (§4.2), where every question is
   impossible to answer, to see if the agent makes something up.

All comparisons use the structured output (rows, statistics results),
never the narrated text, because the same correct answer can be worded
in many different ways. The baseline uses a short, generic prompt, not
the specialized agents' tuned ones, so we can see the value of the whole
architecture. The monolithic agent uses the *same* tuned prompts as the
real agents, so we can see the value of splitting the work up,
separately from the value of the prompts themselves.

**How scoring works.** Data Query and Visualization answers are scored
by comparing the returned rows (the chart's underlying data, for
Visualization) against the ground-truth rows. The order of the rows
doesn't matter, but the count does - if a row is supposed to appear
twice, it has to appear twice in the answer too - and numbers are
matched with a small tolerance of 0.01. Analysis answers are scored by
comparing the specific statistic returned (the mean, the `t_statistic`,
the regression r², ...) to the ground-truth value, also with a small
tolerance. Only the Report Agent is scored subjectively: I rate it by
hand, because a session summary has no single correct answer to check
against.

**Where the ground truth comes from.** It is not an independently known
answer - it is produced by a script (`src/eval/ground_truth/`) that runs
a hand-written reference SQL query (Data Query, Visualization) or a
hand-written reference analysis plan (Analysis) against the real SQLite
database. No LLM is involved, so it always gives the same result and can be repeated,
but it is only as correct as those reference queries, which I wrote
myself when I wrote each question. The evaluation found and
fixed bugs in two of them (`compute_ttest` §3.5, and an earlier
`compute_regression` target bug), so this is a real dependency, not a
formality.

All three providers are called as plain text-completion models: one
prompt in, one block of text out, no provider tool-use/function-calling
API, no web search, no retrieval built into the call. The LLM's only
inputs are the system prompt, the database schema, and the question, and
it never sees a tool result come back mid-generation. This is about how
the model is called, not about whether real computation happens - it
does. The Analysis Agent's output is a JSON plan that names one of 15
pre-written functions (mean, correlation, regression, PCA, K-Means, ...)
and fills in the parameters; separate, plain Python code (not the
LLM) then actually runs that function against the real data (see §6).
So the model decides *which* analysis to run and with *what* parameters,
but it never writes or executes the analysis code itself, and the only
thing that varies between providers is the model's reasoning, not what
tools it can reach.

Every LLM call in this project uses `temperature=0`, on every provider
(`src/llm/factory.py`). This makes the model's answers close to the same
each time, instead of picking randomly among several likely answers, so
re-running the same benchmark should give close to the same results. It
doesn't make the results perfectly identical every single time - a live
hosted API can still vary a little between calls - but it removes most
of the randomness.

The benchmark has 55 questions: 30 Data Query, 15 Analysis, 10
Visualization, split into easy/medium/hard. With so few questions per
category, one single answer flipping from wrong to right (or the other
way round) moves the percentage a lot: 3.3 percentage points per
question in Data Query, 6.7pp in Analysis, and a full 10pp in
Visualization (only 10 questions there). Keep this in mind everywhere in
this document - a gap of 10pp in Visualization can be just one question.
**§2 and §3 below are
Anthropic `claude-haiku-4.5`, in English** - this was the first run done,
before Spanish/Catalan questions existed, and it stays the main
reference dataset throughout this document. Two bugs found during the
evaluation were fixed and the affected runs repeated; §3.2 and §3.5 have
the before/after. Two other things happened later and are covered
further down, not here: the same 55 questions were translated and run
again in Spanish and Catalan on this same Anthropic model (§7), and a
separate local model (Ollama) was evaluated in all three languages (§5).

The evaluation was then run again in **Spanish and Catalan** on the main
model, with the 55 questions and the 6 report-agent sessions translated.
The reference SQL and ground truth are the same (they don't depend on
language) and the system prompts stay in English. §7 compares the three
languages.

---

## 2. Primary results (Anthropic, Claude Haiku 4.5, English) — current, post-fix

### 2.1 Correctness

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% (28/30) | 76.7% (23/30) | 90.0% (27/30) | +16.7pp | +3.3pp |
| Analysis | 100% (15/15) | 40.0% (6/15) | 80.0% (12/15) | +60.0pp | +20.0pp |
| Visualization | 90.0% (9/10) | 50.0% (5/10) | 100% (10/10) | +40.0pp | -10.0pp |

"pp" means percentage points, the plain difference between two
percentages (e.g. 93.3% minus 76.7% is 16.7pp, not "16.7%"). Used
throughout this document wherever two percentages are compared directly.

The Analysis figures reflect two corrections made during the evaluation
(before them: baseline 20.0%, monolithic 86.7%, architecture value
+80.0pp): a bug in `compute_ttest` (§3.5) and a limitation in this
evaluation's own scoring logic (§3.2), both with before/after evidence
below.

### 2.2 Routing accuracy

**90.9% overall** (50/55). Per category: Data Query 100%, Visualization 100%,
Analysis 66.7%. Unaffected by the fixes above (routing behavior didn't
change; only how correctness is scored and computed did).

This number is a floor, not the true error rate. It's measured against
the dataset's `expected_agent` label, but some questions two agents can
both answer correctly. Checking the 5 misrouted questions by hand
against the ground truth (§3.4), all 5 were answered correctly by the
agent they were sent to - so by answer quality the routing here is
effectively 100%. Automating this check in the pipeline benchmark is
future work (§9).

### 2.3 Latency

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Category | Agent-only | Full pipeline | Baseline | Monolithic |
|---|---|---|---|---|
| Data Query | 1.117s | 3.500s | 1.078s | 1.127s |
| Analysis | 1.367s | 3.817s | 5.086s | 1.366s |
| Visualization | 1.710s | 4.940s | 1.628s | 1.640s |

The baseline's Analysis latency (5.086s) is much higher than every other
cell in this table. That matches §3.5: it now writes a more complex
manual SQL query (per-group mean, count, min, max, and a standard
deviation done with a subquery) instead of a short, simple one.

The full pipeline is 3-4x the agent-only time because it makes three LLM
calls (router, then agent, then narrator) instead of one. This is the
price of the architecture. On a fast hosted model it's a few seconds and
doesn't matter much; on a slow local model it multiplies (three calls of
15-40s each on the test laptop - see §5), so the overhead matters more
for a local, private deployment. All these numbers are also
machine-dependent: they were measured on the setup in §5, not tuned
hardware.

### 2.4 Retry / self-correction

The Data Query, Analysis and Visualization agents share a small
self-correcting loop (`src/core/retry.py`): the LLM produces a SQL string
or a JSON plan, it runs, and if that raises an error the error message is
fed back to the LLM and it tries again, up to 3 attempts. "Retry rate" is
the fraction of questions where this loop fired at least once.

**Retry rate: 0% in every category** (Anthropic English), unchanged by
the fixes. The 55-question benchmark never triggered the loop; the
Report-Agent session with impossible questions (§4.2) is the first time it fired, and
it did not recover. It first *succeeded* in the Anthropic Catalan run
(§7.3), and fired a few more times in the Ollama runs (§5).

---

## 3. Failure analysis

### 3.1 The "how many orders" problem

`COUNT(order_id)` gives 9,994 (every line-item row); `COUNT(DISTINCT
order_id)` gives 5,009 (real order transactions, since one order can
have several line items). Claude always picks the DISTINCT version
whenever "orders" is counted. This even changes who "wins" on "which
customer placed the most orders" - "Emily Phan" under DISTINCT vs.
"William Brown" under the ground truth's convention. Not affected by
the two fixes below.

### 3.2 FIXED: a real limitation in the evaluation's own scoring, not in what the baseline can do

**Original finding**: the baseline scorer assumed a plain SQL model
could only ever manage simple statistics like a mean; correlation,
covariance, and t-test were marked `incorrect` automatically, no matter
what the baseline actually returned, on the assumption they can't be
written as one SQL query. That assumption was wrong: Claude's baseline
worked out the exact Pearson correlation formula by hand in SQL
and matched the real system's value almost exactly, but was still marked
wrong just because of how the scorer was written.

**Fix applied**: `check_baseline_analysis` now actually checks the key
number for correlation, covariance, and t-test (comparing the specific
value, e.g. `t_statistic`, against what the baseline returned), instead
of automatically marking them wrong. Regression, PCA, and K-Means are
still automatically marked wrong, and correctly so - those need repeated optimization or matrix
math that one plain SQL `SELECT` really cannot do. That's a real limit
of SQL, not just an assumption in the scorer.

**Effect, confirmed by the re-run**: baseline Analysis correctness went
from 20.0% to 40.0%. Not because the baseline got better - it was always
this capable, the evaluation just wasn't giving it credit. Checked
directly: the baseline's correlation answers (Q5, Q13) now score correct
where they didn't before, with no change to what the baseline actually
does.

**A note on what the baseline can and can't do.** 3 of the 15 Analysis
questions - linear regression (Q10), PCA (Q11) and K-Means (Q12) - cannot
be done in a single SQL query at all. They need many repeated steps, or matrix math, and one `SELECT`
can't loop or work through steps like that. This is a
limit of the tool, not the model: no LLM, however capable, can answer
these when its only tool is "write one SQL query." The baseline is
scored wrong on all 3 by design, because being able to do them is part
of what the specialized agents add. This does make the raw difference look a little bigger than it should,
though - the most the baseline could ever score on Analysis is 12/15,
not 15/15.
On the 12 Analysis questions that SQL can answer, the Anthropic baseline scores
50% (6/12) and the architecture value is +50pp, versus 40% and +60pp
over all 15. Both are true; the conclusion (the architecture is much
better on analytical questions) is the same either way. This only
affects the baseline comparison - the monolithic agent has the same
Python tools as the real agents, so decomposition value (§2.1) is a
clean comparison on these questions.

### 3.3 The chart grouping problem

"Line chart of profit over time for the East region in 2017" never says
how to group the dates. The real Visualization agent and the baseline
both grouped by `order_date` (day by day) and were marked wrong against
a ground truth that groups by month; the monolithic agent grouped by
month (`strftime('%Y-%m', ...)`) and matched. This one question is the
whole -10pp "decomposition value" in Visualization at n=10 - the
monolithic agent isn't better at this task in general, it just guessed a
different (and here, matching) grouping on a question that never
said which one to use.

### 3.4 Routing errors

All 5 routing misses (55 questions, routing accuracy 90.9%) are the same
pattern: an average/median question sent to Data Query instead of
Analysis - "average discount given to customers", "median profit",
"average profit in the West region", "average sales in the East region
for the Furniture category", "median sales value in the South region".
Data Query and Visualization routing were 100%.

**These 5 are not real errors - the Data Query agent answered all of them
correctly.** A mean or median is just `AVG(...)` or a percentile query,
so a question like "what is the average discount" can be handled by
either agent. Checked against the ground truth: the Data Query agent
returned 0.156 (avg discount), 8.67 (median profit), $33.85 (avg profit
West), $346.57 (avg sales East/Furniture) and $54.66 (median sales
South) - all correct. So the router picking Data Query here is a
reasonable choice on a genuinely unclear question, not a failure. The
90.9% figure counts them as failures because it compares against a fixed
label.

This is not always harmless, though. In the Ollama run (§5) the router
misroutes the *opposite* way - it sends ranking questions ("which region
has the highest sales", "which state sold the most") to the Analysis
agent, whose fixed menu of scalar statistics genuinely cannot group and
rank. Those misroutes produce wrong answers that sound completely sure of themselves. So
whether a misroute matters depends on which direction it goes and
whether the receiving agent can actually do the task.

### 3.5 FIXED: `compute_ttest` now compares two groups, not two arbitrary columns

**Original finding**: `compute_ttest` ran a t-test between two numeric
*columns* directly (e.g. discount vs. profit), which is not what a
t-test is for - a t-test compares one variable across two *groups* (e.g.
profit in the Consumer segment vs. the Corporate segment). This was
already a known limitation, and the evaluation showed it had a real
effect: the Report Agent's Session 5 described this test's result as "a
negative correlation," which a t-test doesn't even measure - a wrong
claim in a real generated report, not just a theory problem.

**Fix applied**: `AnalysisPlan` now has explicit `group_column` and
`group_values` fields (exactly 2 group values required), `compute_ttest`
splits the data into two real groups and compares them properly, and the
benchmark question was rewritten from the old unclear phrasing to a real
group-comparison question ("is there a significant difference in profit
between the Consumer and Corporate segments?").

**Effect, confirmed by the re-run**: the real Analysis Agent and the
monolithic agent both now give a correct result, `t_statistic=-0.856,
p=0.392`, group means $25.84 (Consumer, n=5,191) vs. $30.46 (Corporate,
n=3,020) - matching the ground truth exactly. **The Report Agent's
re-generated Session 5 confirms the fix worked end to end**: it now
correctly says "there is not a statistically significant difference...
the p-value of 0.392 is well above the standard significance threshold
of 0.05," replacing the old wrong correlation claim. This is one of the
few cases in this evaluation where a problem wasn't just written down
but actually fixed and checked at every level - unit test, integration
test, and the generated report itself.

### 3.6 Small formatting misses and the row-cap ordering issue

Minor issues, not worth a fix: `SELECT *` instead of the requested
columns; pre-binned histograms as a different (not wrong) way to show
the same thing; and the `MAX_ROWS` + `ORDER BY` interaction, where
*which* rows come back depends on the sort order once a result goes
over the 1,000-row cap.

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

Session 5's ratings went from 2/5 (accuracy) and 2/5 (no fabrication) to
5/5 on both. That's a direct result of the `compute_ttest` fix in §3.5,
not just a different reading of the same report. The re-generated report
is accurate, hedges correctly, and doesn't get the statistical test
wrong anymore. Mean accuracy and no-fabrication across all five sessions
went from 3.4/5 to 4.0/5 because of this one fix.

Sessions 1, 2, and 4 weren't touched by the fixes and keep their old
ratings: Session 1 makes up a profit-margin number nobody asked for
(no-fabrication 2/5); Session 4 has small arithmetic errors and mixes up
which turn a number came from.

### 4.2 Session 6: behavior on impossible questions

This session checks something the other five can't: when the agents fail
or get asked for something the data doesn't have, does the Report Agent
say so, or does it make up a finding? All six questions can't be answered
from the Superstore data (missing column, a customer that doesn't exist,
a metric we don't collect, a country not in the data, a "why" question,
a chart of a column that isn't there). Rated with a failure-focused
template instead of the normal one.

**Model: Anthropic Claude Haiku 4.5. Language: English.**

| Dimension | Score | Justification |
|---|---|---|
| No fabrication | **2/5** | The report states the Q6 chart was "successfully generated ... revealing a positive correlation between [sales and profit]" - a finding no agent computed - and files the request (asked as "employee salary vs profit", a column that does not exist) under **Successful Queries** as a plain "sales vs profit" analysis, so the impossible request disappears. It does *not* invent customer-age or marketing-spend values, and the 2016 monthly figures it cites match the structured query rows it received, so this is a 2, not a 1. |
| Failure transparency | **3/5** | Two of the three failures (customer age, marketing spend) are listed under "Failed or Incomplete Queries" with correct reasons. Q5 is handled well: the report repeats the agent saying there's no clear 2016 decline. But Q6's impossibility is hidden entirely, and Q1 is described as a "system security restriction" rather than a missing column. |
| Completeness | **4/5** | All six questions are in "Questions Asked" and each is covered in the body. Docked one point because Q6 is shown as something other than what was asked. |
| Fluency | **5/5** | Well structured, with a clear "Successful" vs "Failed" split. If anything it reads too confidently: the made-up correlation looks just like the real findings. |

What each agent did with its turn (Model: Anthropic Claude Haiku 4.5.
Language: English.):

| Q | Asked for | Routed to | What happened |
|---|---|---|---|
| 1 | Average customer age (no such column) | data_query | Errored, but with the wrong message: the SQL failed the safety check (`UnsafeSQLError: Only SELECT queries are allowed`) instead of a clear "no such column: age". 3 retries, all rejected. |
| 2 | Sales for customer "Jonathan Q. Fakename" (doesn't exist) | data_query | Correct. Query returned null; the narration said there are no records and the customer may not exist. |
| 3 | Correlation of "marketing spend" with profit (no such column) | analysis | The planner quietly put `sales` in place of the missing column (`"columns": ["sales", "profit"]`), then added a note that broke the JSON parsing, so it failed with a `ValueError` after 3 retries. If the JSON had been clean it would have computed a sales-vs-profit correlation and called it "marketing spend". |
| 4 | Orders shipped to Germany (data is US-only) | data_query | Correct. Returned 0; the narration says no matching records (it doesn't mention that the data is US-only). |
| 5 | "Why did profit decline in 2016?" (false premise) | data_query | Best handling of the six. It pushed back ("I cannot confirm that profit declined overall in 2016"), gave the real monthly numbers, and said 2015 data would be needed to compare. No made-up answer. |
| 6 | Scatter of "employee salary" vs profit (no such column) | viz | The chart engine actually plotted `Sales` vs `Profit` (the saved file is titled "Sales versus Profit per Order"), but the narration kept calling it "Employee Salary vs Profit" and made up a "Salary range: $14.62 to $957.58". Reported as a success. |

Things worth knowing:

- The main problem happens earlier in the pipeline, not in the Report
  Agent: the Data Query and Analysis planners quietly swap `sales` in
  for a missing column (Q3 and Q6 both did this). The Report Agent
  mostly just repeats what it's given.
- The Report Agent actually sticks closer to the real data than the
  narration does. For Q6 it used the structured chart data (labelled
  Sales/Profit) and so
  didn't repeat the "employee salary" mistake, but it also didn't say
  the request was impossible, and it added a "positive correlation"
  claim nobody computed.
- The retry loop ran for the first time here (Q1 and Q3, `attempts: 3`)
  but didn't recover, because a missing column isn't a syntax error a
  retry can fix (see §6).
- For the clearest cases (customer age, marketing spend, missing
  customer) the report invents nothing and marks them as unavailable.
  The risk is in the cases where an agent half-answered with a
  substituted column and passed a normal-looking result up.

---

## 5. Other model providers (Groq, Ollama)

Anthropic (Claude Haiku 4.5) is the primary dataset (§2). Ollama was also
run earlier in the project, but that *original* run is not reported as a
result (§5.1 explains why). A clean re-run on the current system was
done for this document instead, and its real numbers are in §5.3-5.7.

### 5.1 What happened with each

**Groq.** I tried to run the evaluation on Groq, but ran into a few
issues: the model I originally planned to use was retired by the
provider, and the replacement model hit the free tier's rate limit
partway through a run. No Groq numbers are reported anywhere in this
document.

**Ollama (`llama3.1:8b`, local).** The benchmark was also run on this
model earlier, but the result files were overwritten by a later run
before they were committed, so only the aggregate numbers were ever
recorded - no per-question detail survives from that run. A clean re-run
on the current system was done for this document instead, for **all
three languages** - see the real numbers in §5.3-5.7, not the old ones.
Each language needed a multi-hour session on this hardware (§5.6).

### 5.2 Provider trade-offs seen during development

- **Anthropic** - fast, reliable, no rate-limit trouble across the whole
  evaluation. Costs money per token (small for this benchmark, but real).
- **Ollama (local)** - free and private, but slow on a normal laptop
  (CPU only): ~12-20 s per question once warm, 160-340 s to load the
  model the first time, several hours for a full run, and it holds the
  CPU at 100% (the machine runs hot) the whole time.

**On the Ollama re-run specifically:** it was done in stages with
deliberate rest breaks between them (20-30 minutes) to keep the laptop
from overheating during multi-hour runs. Whether the breaks actually
helped is unclear either way - performance still degraded within a
single long run regardless (the Spanish `run_all` took 7.5 hours where
English took about 3, with one warm-up alone taking over 8 minutes -
see the per-language numbers below). So the slowdown looks tied to how long a single run lasts, rather
than something rest breaks between runs fix.
This is stated honestly as something I am not sure about, not as a firm conclusion.

The old Ollama run is gone from this document (§5.1). A **clean Ollama
re-run on the current system** was done for this thesis instead, for
all three languages.
Everything below is real, retained data from
that re-run, in `results/eval/ollama/{en,es,ca}/`.

### 5.3 Ollama correctness, by language

All three languages now have a full run.

**Model: Ollama `llama3.1:8b` (local). Languages: English (EN), Spanish
(ES), Catalan (CA). "real" = real system, "base" = baseline, "mono" =
monolithic agent.**

| | EN real | EN base | EN mono | ES real | ES base | ES mono | CA real | CA base | CA mono |
|---|---|---|---|---|---|---|---|---|---|
| Data Query | 83.3% | 43.3% | 80.0% | 76.7% | 36.7% | 80.0% | 70.0% | 26.7% | 60.0% |
| Analysis | 100% | 33.3% | 80.0% | 93.3% | 20.0% | 40.0% | 93.3% | 20.0% | 33.3% |
| Visualization | 100% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% | 90.0% | 70.0% | 90.0% |

The real system stays close to Anthropic's numbers even on this much
smaller local model (70-100% vs Anthropic's 90-100%), and does better
than Anthropic on Visualization in all three languages. The baseline is
much weaker on Data Query (27-43% vs Anthropic's 77%): a small model
writing raw SQL with no tools makes real mistakes, not just the counting
problem Anthropic runs into (§5.5). Correctness drops a little from
English to Spanish to Catalan, most visibly on Data Query (83 -> 77 ->
70%) and the monolithic agent (80 -> 80 -> 60%). Some of this is just
normal noise from a small model - the actual mistakes are the same kind
in all three languages (§5.5) - but Catalan was also run last, on the
same machine after it had already been under load for many hours (§5.6),
so a real language effect and a tired machine can't be fully told apart
here.

### 5.4 Ollama routing - the real weak point

**Model: Ollama `llama3.1:8b` (local). Languages: English (EN), Spanish
(ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| Overall | 56.4% | 50.9% | 52.7% |
| Data Query | 20% (6/30) | 20% (6/30) | 20% (6/30) |
| Analysis | 100% | 86.7% | 86.7% |
| Visualization | 100% | 90% | 100% |

**Data Query routing is stuck at exactly 20% in all three languages.**
In English, **all 24 misrouted Data Query questions went to Analysis** -
one clear direction. Spanish and Catalan are messier: 23 still go to
Analysis, plus a few elsewhere (Spanish: 1 to the Report agent, 2
Analysis questions to Data Query, 1 Visualization question to Data
Query; Catalan: 1 to the Report agent, 2 Analysis questions to Data
Query). Either way, this model can't reliably tell "retrieve/aggregate
with SQL" apart from "compute a statistic" - the opposite of Anthropic's
routing gap, which went the other way (§3.4).

**And this time it's not a harmless mix-up like Anthropic's.** I checked
what actually happened on each misrouted question (same way as §3.4): in
English, of the 24 misroutes, 9 errored outright, and only 2 of the
remaining 15 landed on the right answer - and even those had the wrong
number attached (e.g. it correctly said "Consumer" is the biggest
segment, but gave an average instead of a total). The rest are just
wrong, stated as if they were right: "the business performs best in the
South region" (it's the West), or a bare dollar figure with no region or
product name attached. Spanish and Catalan show the same pattern. The
Analysis agent's fixed menu (§3.2) can't group-and-rank, so unlike
Anthropic's misroutes, these are answers a real user would see and
believe - it is not just a small detail in how it is scored.

The misrouting also causes outright failures: 10/55 (EN), 8/55 (ES), and
11/55 (CA) pipeline calls failed, almost always because a Data Query
question reached Analysis and it couldn't handle it (`no such column`,
`No numeric columns found`, `Unknown analysis 'sum'` - the model making
up an analysis type that isn't in the menu). Catalan also had one
pipeline call fail for an unrelated reason: the local Ollama server
itself returned an error mid-generation (`unexpected EOF`) - a real
crash, not a reasoning mistake, and consistent with §5.6's finding that
this machine got less stable the longer it ran.

### 5.5 Ollama failure analysis - mostly the same mistakes in all three languages

The Data Query agent's wrong answers repeat **the same mistakes across
English, Spanish, and Catalan**, which tells us something: these are
real weaknesses of the model, not something caused by translation:

- **"Revenue" confused with "profit"**: `SUM(profit)` written where the
  question asks for revenue (`SUM(sales)`) - happened in all three
  languages ("who generated the most revenue", "product with the most
  revenue").
- **Min/max of one row instead of grouping first**: `MIN(profit)` or
  `MAX(quantity)` on the raw table, instead of grouping by region/product
  first and then taking the min/max of the *totals* - happened for
  "least profitable region" and "product with the most units sold" in
  all three languages.
- **Correct query, missing `LIMIT 1`**: e.g. "which segment dominates
  sales" or "where does the business perform best" returns every row
  instead of just the top one - in English and Catalan.
- **Wrong column for "how many customers/purchases"**: Spanish used
  `COUNT(*)` instead of `COUNT(DISTINCT customer_id)`; Catalan mixed this
  up even more, summing `quantity` for "how many purchases" instead of
  counting orders at all.

Catalan also has two mistakes not seen in the other two languages:

- **Region confused with State.** Twice, a question that named "state"
  ("which state sold the most products", "which state had the highest
  total profit") got grouped by `region` instead - two different
  location columns mixed up, not just a wrong aggregate.
- **Picking the wrong replacement analysis.** Asked to cluster orders
  into 3 groups, the model wrote "the analysis you're looking for is
  actually 'groupby', but since it's not a valid analysis type, I'll
  assume you want... 'describe'" - and mixed this explanation into the
  JSON output, breaking it. Interesting because the model correctly
  noticed clustering wasn't literally named "groupby" in its menu, then
  guessed a completely unrelated replacement ("describe", a simple
  summary) instead of the actual K-Means option. This happened on the
  same clustering question in both Session 5 and the standalone Analysis
  benchmark.

One possible language-sensitive slip (a few data points, still not
conclusive): the Spanish "¿cuál es el descuento **medio**?" (average
discount) was planned as `median`, not `mean` - "medio" (average) and
"mediana" (median) may have been confused. Catalan showed a related
pattern on the impossible customer-age question (§5.7): rather than
refuse outright, it reasoned that age could be "approximated by the
average order date" - a real attempt at a workaround, not a refusal or a
made-up number, that happened to fail on a JSON formatting error
before it could act on that idea.

The one Visualization miss in each language is the familiar §3.3
grouping problem, not a new failure - English, Spanish, and Catalan
(and separately, via Anthropic, §7.4) have all shown different
grouping guesses on the same chart question, which never says how to group the data. Spanish
and Catalan both chose to group by *year* (a single data point for the
whole "line chart"), an even coarser guess than daily or monthly.

### 5.6 Ollama latency, and the machine slowing down over long runs

**Model: Ollama `llama3.1:8b` (local). Languages: English (EN), Spanish
(ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Agent-only (DQ/An/Viz) | 12.5 / 13.7 / 19.8 s | 9.3 / 13.1 / 19.7 s | 12.4 / 16.7 / 16.3 s |
| Full pipeline (DQ/An/Viz) | 54.9 / 65.8 / 129.3 s | 44.5 / 62.3 / 143.8 s | 71.9 / 46.6 / 71.5 s |
| Retry rate | DQ 3.3%, Viz 10% | DQ 6.7%, Viz 10% | Analysis 6.7% (failed) |

10-25x slower than Anthropic, which is expected for local CPU inference.
The more interesting finding: **the machine got slower the longer it
ran, not just because the model is slow.** The English `run_all`
(correctness + pipeline) took about 3 hours; the same Spanish run took
**7.5 hours**, and one report-session warm-up alone took over 9 minutes
(573 s), worse than earlier warm-ups of 100-340 s. I checked this
instead of guessing: the CPU itself was not maxed out (about 50% idle),
but the machine was down to a few hundred MB of free RAM with real swap
use, on a 15 GB laptop already using almost all of that between Windows
and the WSL2 Linux VM running Ollama - there was no spare RAM left to
give it. This looks like the memory slowly filling up over many hours,
not a one-off. Rest breaks between runs were tried but didn't fix it,
because the slowdown builds up *inside* one long run - whether the
breaks helped at all is honestly not clear (§5.2).

The Catalan run adds one more real finding: **the laptop went to sleep
partway through** (checked directly - the system log showed repeated
clock-jump messages, the sign of a machine waking up from sleep), which
paused the benchmark process for a long stretch with no data lost, just
lost time - and separately, the local Ollama server itself crashed once
mid-question (`unexpected EOF`, §5.4). Between this and the memory filling up over time, Catalan is the least stable of the three language runs on this
hardware. None of this affects correctness, only how long everything
took and how many pipeline calls errored.

### 5.7 Ollama Report Agent

Same 6 sessions and rubric as the Anthropic review (§4). Ratings:

**Model: Ollama `llama3.1:8b` (local). Languages: English (EN), Spanish
(ES), Catalan (CA).**

| | EN sessions 1-5 mean | ES sessions 1-5 mean | CA sessions 1-5 mean |
|---|---|---|---|
| Accuracy / Completeness / No-fab / Fluency | 3.0 / 5.0 / 4.2 / 4.6 | 3.2 / 5.0 / 4.2 / 4.6 | 2.8 / 4.6 / 3.2 / 4.6 |

| Session 6 (impossible questions) | No-fab | Failure-transp. | Completeness | Fluency |
|---|---|---|---|---|
| EN | 1 | 2 | 4 | 4 |
| ES | 2 | 2 | 5 | 4 |
| CA | 2 | 2 | 5 | 4 |

Lower accuracy than Anthropic (§4.1's mean was 4.0), which makes sense -
the routing mistakes (§5.4) send several sessions to the Analysis agent
with something it simply can't do, and the report just repeats the
wrong answer. Catalan scores lowest of the three, mainly because of two
sessions with real fabrication (below) rather than routing alone. Things
worth knowing:

- **A serious fabrication that shows up in all three languages.**
  Session 6's "correlation between marketing spend and profit" -
  impossible, no such column - was never reported as a failure in
  English, Spanish, *or* Catalan. Instead the model silently substituted
  a real column and reported a precise, confident correlation as fact
  ("0.48, p=0.0" in English; "-0.219" - the real discount/profit
  correlation - in both Spanish and Catalan). Every other run in this
  project on this exact question (Anthropic in all three languages)
  either errored or refused. This is the worst single fabrication found
  anywhere in the evaluation, and it's consistent across languages on
  this model.
- **The Session 6 "employee salary vs profit" chart, and a case where
  the report undoes what the agent got right.** Made up in English
  (fake salary figures, a claimed "positive correlation"), but in both
  Spanish *and now Catalan* the Visualization agent correctly called it
  "sales vs profit" with real values and no invented relationship - the
  same pattern already seen on Anthropic (§7.5), now confirmed on a
  second model across two separate language runs. But in Catalan the
  *Report Agent* then wrote the summary back using the original
  "employee salary" description anyway - cancelling out the honest
  narration it was given. So getting the underlying answer right doesn't
  guarantee the final report stays honest.
- **A real fabrication invented by the Report Agent itself, not
  inherited from a worker agent.** In Catalan Session 4, the pie-chart
  question failed completely with a technical crash (the local Ollama
  server returned `unexpected EOF` mid-generation, §5.4/§5.6) - there
  was no answer at all for that turn. The Report Agent's summary still
  confidently listed three segment counts for it ("Consumer: 5191,
  Corporate: 3020, Home Office: 1783") as if the question had been
  answered. Those numbers are real values from elsewhere in the dataset,
  but they were never computed or returned in this conversation - the
  report made up a complete, believable-looking answer to cover up a
  turn that had actually crashed. Session 3 shows a smaller version of the
  same thing: raw sample rows from a boxplot got relabelled in the report
  as "median," "first quartile," "third quartile," and "outliers" -
  specific statistical claims nobody computed.

### 5.8 What this means for the Limitations section

The Ollama re-run is real, retained data for all three languages now.
This section is still less complete than the Anthropic evaluation (§2,
§7) in one way: only one translation pass (not independently checked).
A by-difficulty comparison across both models is in §8. The routing
weakness (§5.4) and the marketing-spend fabrication (§5.7) are the two
findings here that don't have an
equivalent on Anthropic - real differences in what the models can do, not
just because of a different setup, since everything else about the
pipeline is identical. Catalan ran last, on a machine that had already
been under load for hours and went through an unplanned sleep and one
server crash (§5.6) - its somewhat lower numbers and the two new report
fabrications (§5.7) may partly reflect that, not just the language.

---

## 6. What this evaluation does and does not establish — for the Limitations section

**Established, with evidence:**
- The specialized multi-agent architecture beats a minimal no-tools
  baseline, clearly and across all three categories (on Anthropic Haiku,
  the reported dataset).
- The architecture also beats a monolithic agent with the same tools and
  prompts (decomposition value: Data Query +3.3pp, Analysis +20.0pp,
  Visualization -10.0pp - the last one is entirely a single unclear
  question, §3.3). Note this compares the monolithic agent against the
  **individual agents in isolation** (correctness benchmark forces
  routing), so it assumes the real system routes perfectly. The routing
  errors (§2.2) are not counted against it. A fairer end-to-end
  comparison (monolithic vs router + agents, routing errors included) is
  future work (§9).
- **A real correctness bug (`compute_ttest`) and a real evaluation
  scoring limitation were found, fixed, and the fix independently
  verified at three levels** (unit test, integration test against real
  ground truth, and a re-generated Report Agent session), a real
  example of the evaluation process finding and fixing real
  problems, not just producing a number.
- Routing errors mostly happen where Data Query and Analysis overlap
  (simple totals and averages), not spread out randomly.
- **The architecture beats the baseline on a second, much weaker model
  too** (Ollama `llama3.1:8b`, all three languages, §5.3) - real-system
  correctness stays within about 10-20pp of Anthropic's on English and
  Spanish, dropping further on Catalan (also the run most affected by
  machine issues, §5.6), while the baseline is much worse in every
  language. But routing quality does not transfer: the same small model
  that is close to Anthropic in raw ability misroutes about 80%
  of Data Query questions in all three languages (§5.4), and unlike
  Anthropic's routing gaps these produce genuinely wrong answers, not
  just a scoring mismatch.
**Scope / design choices (state these, they are deliberate):**
- **Closed-world, and no LLM-written code.** The system has no internet
  access and no agent writes or runs its own code - full detail in
  `docs/architecture.md` (Current Limitations). Two consequences for
  this evaluation specifically: questions needing outside context ("why
  did sales drop in 2017", "is a 12% margin good", industry benchmarks)
  are out of scope, and the Analysis Agent can only answer what its 15
  pre-written functions cover (§3.2 has what that means for the
  baseline comparison).

**Not established, and should be stated as open questions:**
- **The baseline can't do 3 of the Analysis questions at all** (regression,
  PCA, K-Means - cannot be written as one SQL query, §3.2). It is scored
  wrong on those by design. The architecture value is +60pp over all 15
  Analysis questions and +50pp over the 12 that SQL can express; the
  headline number uses all 15.
- Retry/self-correction effectiveness: first tried out in the session with
  impossible questions (§4.2), where the loop fired (`attempts: 3`) on two turns but
  could not recover because the fault was a missing column, not a
  correctable syntax error. The **first successful** self-correction in
  the whole evaluation was in the Catalan run (§7.3): one Analysis plan
  failed to parse, retried, and the second attempt scored correct. Still
  only two data points; the English 55-question benchmark showed a 0%
  retry rate.
- Whether decomposition value would hold at a larger question count.
- **Latency was not a focus.** The architecture costs time - three LLM
  calls per question instead of one (§2.3). On a hosted model that's a
  few seconds; on a local model it's much more, and there is a large
  one-off cost the first time a local model answers after being idle
  (loading the 5-6 GB model into memory took 100-340 s on the test
  laptop; the benchmark warms up before timing so this doesn't distort
  the per-question numbers). All latency figures are from one modest
  machine (a low-power laptop, CPU only), not tuned hardware.
- **Cross-provider results.** Anthropic Haiku is the primary, complete
  dataset. Ollama (`llama3.1:8b`) has a real re-run on the current
  system for all three languages (§5.3-5.7), with the Catalan run
  affected by machine issues (§5.6). A by-difficulty comparison of both
  models is in §8. Cost per provider was not measured.
- **The multilingual evaluation (§7) is Anthropic Haiku only** - the
  Ollama multilingual comparison (§5.3-5.7) is a separate, smaller
  exercise (all three languages, but fewer dimensions measured, and the
  Catalan run affected by machine issues).

---

## 7. Multilingual evaluation (Spanish and Catalan)

The evaluation was run again with the 55 questions and the 6 Report-Agent
sessions translated into Spanish and Catalan, to see if the language of
the question changes anything. This section is Anthropic Claude Haiku
4.5 only. Ollama has its own three-language results in §5.3-5.7 (a
different local model, run and written up separately).

### 7.1 Method

- The translations are in the dataset files. `question` is now a dict
  `{en, es, ca}`, so there is still one file per category with one copy
  of the reference SQL and the ground truth.
- The ground truth is not changed. The reference SQL and the expected
  answers are the same in every language, and scoring compares the
  returned rows and numbers, not the text.
- Value names are kept in English in all three languages: `West`,
  `Technology`, `Consumer`, `Second Class`. So the test is about the
  language of the question, not about translating a value name back to
  what is stored in the database.
- The system prompts are left in English. This tests the system as it
  is, not a version tuned for other languages. A "answer in the user's
  language" prompt is left for future work.
- Output is in `results/eval/anthropic/{en,es,ca}/`.

### 7.2 Correctness by language

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish
(ES), Catalan (CA).**

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

The real system does about the same in all three languages. Real-system
correctness stays between 90% and 100% everywhere. The small changes
(Data Query 93.3 to 100 in Catalan, monolithic Analysis 80 to 93.3 in
Spanish) are caused by the two known unclear points in §7.4, not by the
model being worse or better at a language. The baseline also fails on the
same questions in every language (see §7.4).

### 7.3 Routing, latency, retry by language

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish
(ES), Catalan (CA). DQ = Data Query, An = Analysis, Viz = Visualization.**

| | EN | ES | CA |
|---|---|---|---|
| Routing accuracy — overall | 90.9% | 92.7% | 90.9% |
| Routing accuracy — Data Query | 100% | 100% | 96.7% |
| Routing accuracy — Analysis | 66.7% | 73.3% | 73.3% |
| Routing accuracy — Visualization | 100% | 100% | 100% |
| Agent-only latency — DQ / An / Viz (s) | 1.12 / 1.37 / 1.71 | 1.05 / 1.17 / 1.71 | 1.02 / 1.33 / 1.71 |
| Full-pipeline latency — DQ / An / Viz (s) | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 |
| Retry rate | 0% | 0% | 6.7% (Analysis) |

Routing works about the same in every language, and the misroutes are
the same as §3.4: average/median questions going to Data Query instead
of Analysis (4-5 per language). Catalan has one extra misroute that the
others don't - "Quin client va fer més comandes?" ("which customer made
the most orders") went to Analysis.

One thing worth noting: the first time the retry loop actually recovered
in the whole project was here. In the Catalan Analysis run, question 1's
plan came back as invalid JSON, the loop retried, and the second try was
correct (`attempts: 2`, `correct: true`). Latency is a bit lower in
Spanish/Catalan for Data Query and a bit higher for Visualization, but
the gaps are small.

### 7.4 Are the wrong answers real errors? (all three languages)

Every wrong answer from the real agents, in every language, is one of the
two unclear points already described in §3 - none of them is the model
misunderstanding Spanish or Catalan:

- **The order-counting problem (§3.1).** For "how many orders", "orders
  by Second Class", "category with the most orders", "order count by
  segment", the agent uses `COUNT(DISTINCT order_id)` (5,009 orders,
  which §3.1 argues is the sensible reading) while the ground truth uses
  `COUNT(*)` (9,994 line items), or the other way round. Which one it
  picks changes with the language and the run: English and Spanish are
  marked wrong on "how many orders" (they chose DISTINCT), Catalan
  matches the ground truth there; the "order count by segment" chart
  flips the other way (English matches, Spanish and Catalan don't). These
  are scoring mismatches on an unclear question, not real mistakes.
- **The chart grouping problem (§3.3).** The "profit over time, East
  region, 2017" line chart, daily vs monthly. English missed it; Spanish
  and Catalan picked monthly and passed.

If you set those two aside, the real system is basically 100% correct in
all three languages.

The baseline fails on the same questions in every language, for good
reasons: SQLite has no `MEDIAN` / `STDEV` / `VAR_POP` function, and you
can't do linear regression, PCA or K-Means in one `SELECT`. The
monolithic agent's few extra misses are the vague questions ("where does
the business perform best", "which segment dominates sales") plus, in
Catalan only, one JSON parse error.

### 7.5 Report Agent by language

Same 6 sessions, translated. The ratings below are my own pass, done the
same way for all three languages; the English column matches §4.1 within
about ±0.2. Per-session scores with a short reason each are in the
`results/eval/anthropic/{es,ca}/report_agent_review.md` files. Means:

**Model: Anthropic Claude Haiku 4.5. Languages: English (EN), Spanish
(ES), Catalan (CA).**

| | EN | ES | CA |
|---|---|---|---|
| Sessions 1–5 mean — Accuracy / Completeness / No-fabrication / Fluency | 4.0 / 5.0 / 3.8 / 5.0 | 4.2 / 5.0 / 3.8 / 5.0 | 3.8 / 5.0 / 3.4 / 5.0 |
| Session 6 (impossible questions) — No-fab / Failure-transparency / Completeness / Fluency | 2 / 3 / 4 / 5 | 3 / 3 / 5 / 5 | 3 / 3 / 5 / 5 |

The one clear difference by language: **the report is always in English.**
In the Spanish and Catalan sessions everything else is in the right
language - the questions, the agent answers, even the number format
("725.457,82", "-0,219", "9,82 anys") - but the Report Agent always
writes an English document, and its "Questions Asked" section puts the
questions back into English. The narrator follows the user's language;
the report agent doesn't, because its prompt is English and says nothing
about language.

Other things:

- The report's usual mistakes are the same in every language. Session 1
  invents a made-up profit-margin number in all three (English and
  Catalan "~39%", Spanish "5.7%", which is also just wrong math). Session
  4 gets the segment percentages a bit wrong in English and badly wrong
  in Catalan (they add up to 114%); Spanish gets them right.
- Session 6 was actually handled better in Spanish and Catalan than in
  English. For the impossible "employee salary vs profit" chart, the
  English viz agent made up a fake salary axis and the English report
  claimed a "positive correlation"; the Spanish and Catalan agents just
  said "Sales vs Profit" and the reports repeated that without inventing
  a finding. This is luck (the narrator didn't pick up the false premise
  in es/ca), but it happened.
- Session 6 "average customer age" also went differently. English hit a
  hard error (the SQL failed the safety check); Spanish and Catalan
  returned a wrong "9.82 years" (the SQL measured order age) - both the
  narration and the report flagged it as odd, but the report still lists
  it as "✓ Success, 9.82 years".
- Sessions 2, 3 and 5 are good and about the same in all three languages
  - correct stats, correct t-test wording, correct clusters.

### 7.6 What this part shows

- The system handles Spanish and Catalan about as well as English.
  Correctness, routing and latency are all close to the English numbers.
  No new kind of failure shows up - every wrong answer is one of the two
  unclear points from the English analysis, or a normal baseline limit.
- The one gap is the output: the Report Agent always writes English, even
  when the conversation was in another language. A one-line prompt change
  would fix it; left as future work.
- This was one model (Anthropic Haiku) and one set of translations, done
  by me and not checked by anyone else.

---

## 8. Overall conclusions

All the benchmarks tag each question `easy`, `medium`, or `hard`, and the
evaluation scripts already compute correctness split by that tag - this
was in the raw output the whole time (`summary.csv` for every run) but
never pulled together into one place. Doing that, and putting it next to
the language and model comparisons already in this document, gives a few
findings that are not visible from any single table above.

**By difficulty.** Real-system vs. baseline correctness, averaged across
English, Spanish, and Catalan for each model (Anthropic Claude Haiku 4.5;
Ollama `llama3.1:8b`, local):

| | Easy: real / base | Medium: real / base | Hard: real / base |
|---|---|---|---|
| Anthropic - Data Query | 90.0% / 73.3% | 96.7% / 80.0% | 100% / 76.7% |
| Anthropic - Analysis | 100% / 33.3% | 100% / 66.7% | 100% / 16.7% |
| Anthropic - Visualization | 77.8% / 66.7% | 100% / 75.0% | 88.9% / 22.2% |
| Ollama - Data Query | 90.0% / 60.0% | 73.3% / 30.0% | 66.7% / 16.7% |
| Ollama - Analysis | 88.9% / 44.4% | 100% / 38.9% | 94.4% / 0% |
| Ollama - Visualization | 100% / 100% | 100% / 75.0% | 77.8% / 33.3% |

Two things stand out:

- **The baseline loses the most ground on hard questions, in both
  models.** That is where the architecture earns its keep the most, not
  the least. Anthropic's baseline drops to 16.7-22.2% correct on hard
  Analysis and Visualization questions, while the real system stays at
  88.9-100%. Same shape on Ollama, lower floor (0-33.3% baseline).
- **But the Analysis "hard" collapse is mostly about how the questions
  are labeled, not pure difficulty.** The hard-tier Analysis questions are exactly the
  ones that need regression, PCA, or K-Means (§3.2) - the baseline can't
  express those in one SQL query no matter how easy the underlying idea
  is. So "hard" here partly means "needs a tool the baseline doesn't
  have," not just "a harder question of the same kind." Data Query and
  Visualization hard questions are a fairer test of raw difficulty, since
  the baseline *can* attempt them in SQL - and there the baseline still
  drops with difficulty (Anthropic 73.3% to 76.7%, roughly flat; Ollama
  60% to 16.7%, a real decline).
- **Anthropic's real system is barely affected by difficulty; Ollama's
  is.** Anthropic real-system correctness stays at 88.9-100% at every
  difficulty tier and every category (the one dip, Visualization easy at
  77.8%, is the single order-counting problem from §3.1, not a real
  difficulty effect). Ollama's real system, on the other hand, visibly
  drops from easy to hard on Data Query (90.0% to 66.7%) and
  Visualization (100% to 77.8%) - a real gap in what the model can do, for a much
  smaller model, not just noise, and it lines up with the specific
  mistakes in §5.5 (grouping and ranking mistakes cluster on the harder
  questions).

**By language.** The point of testing three languages was to see if
language is an issue for this system at all. Going in, there was a real
reason to expect it might not be a fair fight between the three: English
is by far the most common language in the text LLMs are trained on,
Spanish is also widely used online but with less of it, and Catalan is a
minority language with much less text available anywhere - so a model
could reasonably be expected to know it less well, and perform worse on
it, in that order (English, then Spanish, then Catalan).

Anthropic is flat across English, Spanish, and Catalan (§7.2, §7.3) -
correctness, routing, and latency all stay within a few points of each
other, and every wrong answer comes from one of the two scoring
problems already documented (§3.1, §3.3), not from the model struggling
with Spanish or Catalan. So on this model, the expected English > Spanish
> Catalan pattern doesn't really show up - a strong hosted model seems
to have more than enough of each language to handle a closed-world task
like this one equally well. Ollama does not hold as flat: correctness
declines from English to Spanish to Catalan on Data Query and the
monolithic baseline (§5.3), and the Report Agent's worst fabrications of
the whole project happened on the Catalan run (§5.7) - which does match
the expected order, for what that's worth. Catalan was also the run
with the most machine trouble - a sleep event and a server crash
(§5.6) - so some, but probably not all, of that decline may be the
hardware rather than the language itself. The honest conclusion: on a
strong hosted model, language doesn't matter much for this task; on a
small local model, it might, in the direction the relevance of each
language would predict, but this single run can't separate that from
machine fatigue.

**By model.** The one finding that holds up everywhere, on both models,
in all three languages, and at every difficulty tier: **the specialized
multi-agent architecture beats a plain single-prompt baseline.** That is
true even on a much smaller, free, local model that is clearly weaker
than the hosted one in other ways.

**By architecture design (does splitting the work up help, on its
own?).** This is a different question from "beats a plain baseline" -
it's real system vs. the monolithic agent, which has the *same* tools
and prompts but as one agent instead of several (decomposition value,
§1). In percentage points, real system minus monolithic:

| | Data Query EN/ES/CA | Analysis EN/ES/CA | Visualization EN/ES/CA |
|---|---|---|---|
| Anthropic | +3.3 / +6.7 / +6.7 | +20.0 / +6.7 / +13.3 | -10.0 / 0 / 0 |
| Ollama | +3.3 / -3.3 / +10.0 | +20.0 / +53.3 / +60.0 | +10.0 / 0 / 0 |

Splitting the work up helps almost everywhere, but by very different
amounts depending on the model. On Anthropic the gain is modest (0 to
+20pp); the one negative number (Visualization, English) is entirely the
single unclear chart-grouping question from §3.3, not a real pattern. On
Ollama the gain on Analysis is large and grows with each language (+20pp
in English, up to +60pp in Catalan) - splitting the "which statistic do I
compute" decision out into its own focused agent matters much more for a
small model than a strong one, which makes sense: a smaller model has
less room to juggle several different tool sets inside one prompt at
once. The one negative number for Ollama (Spanish Data Query, -3.3pp) is
a single question flipping at n=30, not a real reversal either.

**By routing.** Overall accuracy: Anthropic 90.9-92.7% across the three
languages, Ollama 56.4% (EN), 50.9% (ES), 52.7% (CA). But the overall
number hides that the two models fail in different places:

| | Anthropic EN/ES/CA | Ollama EN/ES/CA |
|---|---|---|
| Data Query | 100 / 100 / 96.7% | 20 / 20 / 20% |
| Analysis | 66.7 / 73.3 / 73.3% | 100 / 86.7 / 86.7% |
| Visualization | 100 / 100 / 100% | 100 / 90 / 100% |

Anthropic's weak spot is Analysis (it sometimes sends an
average/median-style question to Data Query instead), and checking the
actual answers shows this barely matters - every misrouted question was
still answered correctly by whichever agent got it (§2.2, §3.4). Ollama's
weak spot is Data Query, stuck at exactly 20% in every language - the
small model can't reliably tell "retrieve/aggregate with SQL" apart from
"compute a statistic," and this time the mistake is not harmless: most of
those misrouted questions come back wrong, stated as if correct (§5.4).
Same kind of mistake (mixing up two similar categories), very different
consequences.

**By latency.** Full-pipeline average, Data Query / Analysis /
Visualization, in seconds:

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 |
| Ollama | 54.9 / 65.8 / 129.3 | 44.5 / 62.3 / 143.8 | 71.9 / 46.6 / 71.5 |

Ollama is roughly 15-30x slower than Anthropic on the same questions,
which is expected for a small model doing CPU-only inference instead of
calling a hosted API. Language changes latency only a little on
Anthropic. On Ollama the numbers move around more (e.g. Catalan Analysis
is actually the fastest of the three), but that is almost certainly the
laptop's own state at the time (§5.6: it slowed down over long runs, and
the Catalan run also had a sleep event and a crash) rather than Catalan
being an easier language to process.

**On retries.** The self-correcting loop (§2.4) fires far more often on
Ollama than on Anthropic. Anthropic only triggered it once in the entire
evaluation (Catalan Analysis, and it fixed itself). Ollama triggers it in most runs, at a rate of 3.3-10% in at least one
category in every language (Data Query and/or Visualization in English
and Spanish, Analysis in Catalan) - because a smaller model produces
more broken SQL and JSON to begin with. But it is also less reliable once triggered: some
Ollama retries fix the problem (English Visualization, 100% success),
some don't (Catalan Analysis - the K-Means/"describe" mix-up in §5.5
survived the retry and still failed). So the retry loop is doing real
work on the weaker model, catching some genuine mistakes, but it is not
a substitute for the model actually understanding the question.

**On honesty (Report Agent).** Same rubric, both models, normal sessions
1-5 (Accuracy / Completeness / No-fabrication / Fluency, out of 5):

| | EN | ES | CA |
|---|---|---|---|
| Anthropic | 4.0 / 5.0 / 3.8 / 5.0 | 4.2 / 5.0 / 3.8 / 5.0 | 3.8 / 5.0 / 3.4 / 5.0 |
| Ollama | 3.0 / 5.0 / 4.2 / 4.6 | 3.2 / 5.0 / 4.2 / 4.6 | 2.8 / 4.6 / 3.2 / 4.6 |

Surprising at first: Ollama's no-fabrication score on normal
sessions is not worse than Anthropic's, sometimes a touch better. The
gap is in accuracy, and it's a routing problem more than an honesty
problem - several Ollama sessions ask the Analysis agent something it
simply can't do (§5.4), and the report just repeats that wrong
answer without making anything up. The picture flips on the session with impossible questions,
where every question cannot be answered at all: there,
Ollama's no-fabrication score (1-2 across languages) is worse than
Anthropic's (2-3), and Ollama produced the worst fabrications found
anywhere in the whole project - a confident, precise, entirely invented
correlation number in all three languages (§5.7), a complete answer made
up for a turn that had actually crashed, and sample rows mislabeled as
computed statistics (§5.7, Catalan). So a model can look equally honest
on ordinary questions and still be much more willing to make something up
the moment there is genuinely nothing true to say.

**Bottom line.** The architecture's core promise - specialized agents
with real tools beat one generic prompt - holds up everywhere this was
tested: three languages, two very different models, every difficulty
tier. Splitting that same toolset across separate agents (instead of one
agent with all of them) helps too, and it helps the weaker model more
than the stronger one. What changes between models is everything that
follows from those two points: which category the router gets wrong
(and how much it costs when it does), how often self-correction is even
needed, how fast the answer comes back, and how the system behaves when
a question genuinely cannot be answered. A smaller, free, local model is
a real option for the core task, but it needs a better router and closer
supervision of its Report Agent before it could be trusted the way the
hosted model was here.

---

## 9. Future work

This is the one place in the repo for ideas on what to build or change
next. What the system can't currently do is listed separately, in
`docs/architecture.md` (Current Limitations) - this section is about
fixing or extending those, not restating them.

- **Make the agents actually cooperate.** Right now each agent is
  independent - the router picks one, it runs, done. They could pass
  results to each other directly (e.g. Analysis using a Data Query
  result as input), instead of only ever going through the orchestrator,
  or a planner could chain several agents for one question.
- **Remember recent turns, not just the current question.** Routing and
  narration only ever see the current question right now. Using the
  last few turns (not the whole history) would let the system
  understand something like "that region," referring back to an earlier
  answer.
- **More agents, or a wider Analysis Agent.** Add agent types
  (forecasting, data quality checks, ...), or widen the Analysis
  Agent's fixed list of 15 functions - for example ANOVA, so it can
  compare more than the two groups the current t-test is limited to, or
  paired samples.
- **A real code-generating agent.** This is a different kind of change
  from the one above - not more pre-written functions, but letting an
  agent write and run its own Python code, so it isn't limited to a
  fixed list at all. Right now no agent does this on purpose (§6): it
  trades away flexibility for safety, a result that's always the same,
  and answers that can be checked against an exact right answer. Doing
  this safely would need real sandboxing - running the generated code
  somewhere isolated, with no access to anything outside that one task -
  and a way to still check its answers, since a code-generating agent
  can't be checked against ground truth as directly as a fixed list of
  functions can.
- **Score the pipeline answers automatically.** The pipeline benchmark
  only records routing and latency, not whether the final answer was
  right. The misrouted questions were checked by hand here (§3.4), but
  automating it would give two things: a real "routing quality by answer"
  number, and a fair end-to-end comparison of the monolithic agent vs the
  full system as a user hits it (router + agents, routing mistakes
  included) instead of vs the agents with routing forced correct (§2.1).
- **Reduce the Data Query / Analysis routing overlap.** Right now a
  mean, median, or other simple statistic can be answered correctly by
  either agent (§2.2, §3.4), so there's no single right routing choice
  for those questions. Either the two agents' jobs could be split more
  clearly (e.g. Analysis only handles anything beyond a raw count or
  sum), or the benchmark's "expected agent" label could allow more than
  one correct agent per question, so routing accuracy measures real
  mistakes instead of penalizing a defensible choice.
- **A second, harder dataset.** Everything here is on Superstore.
  Running the same evaluation on a larger or messier dataset - or one
  with more than one table (e.g. Olist), to see how well the system
  handles JOINs - would show how much of what was found is specific to
  this one.
- **Answer in the user's language** - the Report Agent's system prompt is
  English-only (§7.5); a one-line change would make it follow the
  conversation language, like the narrator already does.
- **Finish the cross-provider picture** - a real Groq run once a
  suitable model is available, and cost measurement per provider (§5).
- **Fix the Ollama router's Data Query blind spot** (§5.4) - it's the
  single biggest gap found on the local model, and unlike Anthropic's
  routing gaps it produces real wrong answers, not just a scoring
  mismatch. A few more example questions (with their correct agent) in the router prompt would be
  the first thing to try.
- **Full containerization.** Running everything in Docker containers,
  one container per agent (with Docker Compose), for easier deployment.
