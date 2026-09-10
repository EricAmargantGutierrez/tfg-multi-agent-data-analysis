# Evaluation Results and Failure Analysis

## 1. Methodology recap

The system was evaluated along four independent dimensions, each isolating a
different question:

1. **Correctness** — real specialized agents vs. two baselines, per
   category (Data Query, Analysis, Visualization), against ground truth computed
   by direct execution (never by an LLM).
2. **Decomposition value** — the real agents vs. a *monolithic* agent
   with identical tools and identical prompt content (the three
   specialized agents' real system prompts, imported verbatim, not a
   paraphrase) but no architectural split. Isolates whether splitting
   work across agents adds value beyond simply having the tools
   available.
3. **Routing accuracy and end-to-end latency** — measured in a single
   pass through the real orchestrator (router -> agent -> narrator),
   independent of the correctness runs, which deliberately bypass
   routing to isolate each agent's own capability.
4. **Report Agent quality** — checked by hand, not scored: a session
   summary has no single right answer, so it's rated on accuracy,
   completeness, fabrication and fluency. Five normal sessions plus one
   adversarial session (§4.2) where every question is impossible to
   answer, to see if the agent makes something up.

All comparisons use structured output (rows, statistics results), never
narrated prose, which can phrase an identical correct answer many
different ways. The baseline uses a deliberately minimal, generic
prompt, not the specialized agents' tuned prompts, to isolate the value
of the architecture as a whole; the monolithic agent uses the *same*
tuned prompts as the real agents, to isolate decomposition specifically.

The benchmark (55 questions: 30 Data Query, 15 Analysis, 10 Visualization,
stratified easy/medium/hard) was run against three different model
providers over the course of this evaluation. **The Anthropic run
(`claude-haiku-4.5`) is the primary, complete dataset reported below.**
Two issues found during the evaluation were fixed and the affected runs
repeated; §3.2 and §3.5 give the full before/after.

The evaluation was then run again in **Spanish and Catalan** on the main
model, with the 55 questions and the 6 report-agent sessions translated.
The reference SQL and ground truth are the same (they don't depend on
language) and the system prompts stay in English. §7 compares the three
languages.

---

## 2. Primary results (Anthropic, Claude Haiku 4.5) — current, post-fix

### 2.1 Correctness

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| Data Query | 93.3% (28/30) | 76.7% (23/30) | 90.0% (27/30) | +16.7pp | +3.3pp |
| Analysis | 100% (15/15) | 40.0% (6/15) | 80.0% (12/15) | +60.0pp | +20.0pp |
| Visualization | 90.0% (9/10) | 50.0% (5/10) | 100% (10/10) | +40.0pp | -10.0pp |

The Analysis figures reflect two corrections made during the evaluation
(before them: baseline 20.0%, monolithic 86.7%, architecture value
+80.0pp): a bug in `compute_ttest` (§3.5) and a limitation in this
evaluation's own scoring logic (§3.2), both with before/after evidence
below.

### 2.2 Routing accuracy

**90.9% overall** (50/55). Per category: Data Query 100%, Visualization 100%,
Analysis 66.7%. Unaffected by the fixes above (routing behavior didn't
change; only how correctness is scored and computed did).

### 2.3 Latency

| Category | Agent-only | Full pipeline | Baseline | Monolithic |
|---|---|---|---|---|
| Data Query | 1.117s | 3.500s | 1.078s | 1.127s |
| Analysis | 1.367s | 3.817s | 5.086s | 1.366s |
| Visualization | 1.710s | 4.940s | 1.628s | 1.640s |

The baseline's Analysis latency (5.086s) is notably higher than every
other cell in this table, consistent with §3.5's finding that it now
attempts a genuinely more sophisticated manual SQL computation (per-group
mean, count, min, max, and a manually-derived standard deviation via a
correlated subquery) rather than a short, simple query.

### 2.4 Retry / self-correction

**Retry rate: 0% in every category**, unchanged by the fixes. The
55-question benchmark never triggered the self-correcting loop on any
provider; the adversarial Report-Agent session (§4.2) is the first time
it was seen to fire, and it did not recover.

---

## 3. Failure analysis

### 3.1 The "how many orders" ambiguity

`COUNT(order_id)` (9,994 — line-item rows) vs. `COUNT(DISTINCT
order_id)` (5,009 — order transactions). Claude consistently applies the
DISTINCT interpretation everywhere "orders" is counted, including
changing the winning entity on "which customer placed the most orders"
("Emily Phan" under DISTINCT vs. "William Brown" under the ground
truth's convention). Not affected by the two fixes below.

### 3.2 FIXED: a real limitation in the evaluation's own scoring, not the baseline's capability

**Original finding**: the baseline scorer assumed a bare SQL model could
only possibly succeed at scalar statistics; correlation, covariance,
and t-test were scored `incorrect` automatically, regardless of the
actual answer, on the assumption they're structurally inexpressible in
one SQL query. This was falsified: Claude's baseline derived the correct
closed-form Pearson correlation formula manually and matched the real
system's value almost exactly, yet was marked wrong purely by scorer
design.

**Fix applied**: `check_baseline_analysis` now genuinely checks the key
metric for correlation, covariance, and t-test (comparing the specific
number, e.g. `t_statistic`, against what the baseline actually
returned), rather than auto-rejecting them. Regression, PCA, and K-Means
remain auto-rejected, correctly, those require iterative optimization
or matrix decomposition that a single, non-procedural SQL `SELECT`
genuinely cannot express, which is a real structural limit, not an
assumption.

**Effect, confirmed by the re-run**: baseline Analysis correctness rose
from 20.0% to 40.0%, not because the baseline got better, but because
it was already this capable and the evaluation wasn't crediting it
correctly. Verified directly: baseline's correlation answers (Q5, Q13)
now score correct where they previously didn't, with no change to the
baseline's actual behavior.

### 3.3 The chart time-granularity ambiguity

"Line chart of profit over time for the East region in 2017" never
specifies granularity. The real Visualization agent and the baseline
both grouped by `order_date` (daily) and were scored incorrect against a
ground truth that groups by month; the monolithic agent grouped by month
(`strftime('%Y-%m', ...)`) and matched. This one question is the entire
-10pp "decomposition value" in Visualization at n=10 — the monolithic
agent did not do the task "better" in general, it made a different
granularity guess on an under-specified prompt that happened to match
the ground truth's unstated assumption.

### 3.4 Routing errors

All 5 routing misses (55 questions, routing accuracy 90.9%) are the same
pattern: an average/median question sent to Data Query instead of
Analysis — "average discount given to customers", "median profit",
"average profit in the West region", "average sales in the East region
for the Furniture category", "median sales value in the South region".
A genuine Data Query/Analysis boundary ambiguity (a mean *is* expressible
in plain SQL), not random noise. Data Query and Visualization routing
were 100%.

### 3.5 FIXED: `compute_ttest` now compares two groups, not two arbitrary columns

**Original finding**: `compute_ttest` ran an independent t-test between
two numeric *columns* directly (e.g. discount vs. profit), not the
standard meaning of a t-test (one variable, compared across two
*groups*, e.g. profit in the Consumer segment vs. the Corporate
segment). This was a documented, known limitation, and evaluation
confirmed it had a real consequence: the Report Agent's Session 5
described this test's result as indicating "a negative correlation,"
which a t-test does not measure, a misleading claim in a real
generated report, not just a theoretical concern.

**Fix applied**: `AnalysisPlan` now has explicit `group_column` and
`group_values` fields (validated: exactly 2 group values required),
`compute_ttest` splits the data into two real groups and runs the
comparison properly, and the benchmark question itself was rewritten
from the old ambiguous phrasing to a genuine group-comparison question
("is there a significant difference in profit between the Consumer and
Corporate segments?").

**Effect, confirmed by the re-run**: the real Analysis Agent and the
monolithic agent both now produce a statistically valid result, 
`t_statistic=-0.856, p=0.392`, group means $25.84 (Consumer, n=5,191) vs.
$30.46 (Corporate, n=3,020) — matching the independently-computed ground
truth exactly. **The Report Agent's re-generated Session 5 confirms the
fix end-to-end**: it now correctly states "there is not a statistically
significant difference... the p-value of 0.392 is well above the
standard significance threshold of 0.05," directly replacing the
previous misleading correlation claim. This is a rare case in this
evaluation of a finding being not just documented but demonstrably
resolved, with direct before/after evidence at every layer (unit test,
integration test, and the generated report itself).

### 3.6 Format-only misses and the row-cap ordering limitation

Minor, non-fix issues: `SELECT *` instead of the requested columns;
pre-binned histograms as an alternative (not wrong) representation; and
the `MAX_ROWS` + `ORDER BY` interaction, where *which* rows are returned
depends on sort order once a result exceeds the 1,000-row cap.

---

## 4. Report Agent — qualitative results

### 4.1 Normal sessions 1–5 (Session 5 re-rated after the fix)

| Session | Accuracy | Completeness | No fabrication | Fluency |
|---|---|---|---|---|
| 1 — Data Query, easy | 3/5 | 5/5 | 2/5 | 5/5 |
| 2 — Analysis | 4/5 | 5/5 | 4/5 | 5/5 |
| 3 — Visualization | 5/5 | 5/5 | 5/5 | 5/5 |
| 4 — Mixed, realistic | 3/5 | 5/5 | 4/5 | 5/5 |
| 5 — Mixed, hard | **5/5** | 5/5 | **5/5** | 5/5 |
| **Mean** | **4.0/5** | **5.0/5** | **4.0/5** | **5.0/5** |

Session 5's ratings improved from 2/5 (accuracy) and 2/5 (no
fabrication) to 5/5 on both, a direct, measured consequence of the
`compute_ttest` fix in §3.5, not a re-interpretation of the same output.
The re-generated report is accurate, correctly hedged, and does not
misstate what the underlying statistical test measures. Mean accuracy
and no-fabrication scores across all five sessions rose from 3.4/5 to
4.0/5 as a direct result.

Sessions 1, 2, and 4 are unaffected by the fixes and keep their ratings:
Session 1 invents an unrequested profit-margin statistic (no-fabrication
2/5); Session 4 has small arithmetic errors and a cross-turn
misattribution.

### 4.2 Adversarial session (Session 6): behaviour on impossible questions

This session checks something the other five can't: when the agents fail
or get asked for something the data doesn't have, does the Report Agent
say so, or does it make up a finding? All six questions can't be answered
from the Superstore data (missing column, a customer that doesn't exist,
a metric we don't collect, a country not in the data, a "why" question,
a chart of a column that isn't there). Run on the same setup as the rest
of this document (Anthropic Claude Haiku 4.5). Rated with a
failure-focused template instead of the normal one:

| Dimension | Score | Justification |
|---|---|---|
| No fabrication | **2/5** | The report states the Q6 chart was "successfully generated ... revealing a positive correlation between [sales and profit]" — a finding no agent computed — and files the request (asked as "employee salary vs profit", a column that does not exist) under **Successful Queries** as a plain "sales vs profit" analysis, so the impossible request disappears. It does *not* invent customer-age or marketing-spend values, and the 2016 monthly figures it cites match the structured query rows it received, so this is a 2, not a 1. |
| Failure transparency | **3/5** | Two of the three failures (customer age, marketing spend) are listed under "Failed or Incomplete Queries" with correct reasons. Q5 is handled well: the report repeats the agent saying there's no clear 2016 decline. But Q6's impossibility is hidden entirely, and Q1 is framed as a "system security restriction" rather than a missing column. |
| Completeness | **4/5** | All six questions are in "Questions Asked" and each is covered in the body. Docked one point because Q6 is shown as something other than what was asked. |
| Fluency | **5/5** | Well structured, with a clear "Successful" vs "Failed" split. If anything it reads too confidently: the made-up correlation looks just like the real findings. |

What each agent did with its turn:

| Q | Asked for | Routed to | What happened |
|---|---|---|---|
| 1 | Average customer age (no such column) | data_query | Errored, but with the wrong message: the SQL failed the safety check (`UnsafeSQLError: Only SELECT queries are allowed`) instead of a clear "no such column: age". 3 retries, all rejected. |
| 2 | Sales for customer "Jonathan Q. Fakename" (doesn't exist) | data_query | Correct. Query returned null; the narration said there are no records and the customer may not exist. |
| 3 | Correlation of "marketing spend" with profit (no such column) | analysis | The planner quietly put `sales` in place of the missing column (`"columns": ["sales", "profit"]`), then added a note that broke the JSON parsing, so it failed with a `ValueError` after 3 retries. If the JSON had been clean it would have computed a sales-vs-profit correlation and called it "marketing spend". |
| 4 | Orders shipped to Germany (data is US-only) | data_query | Correct. Returned 0; the narration says no matching records (it doesn't mention that the data is US-only). |
| 5 | "Why did profit decline in 2016?" (false premise) | data_query | Best handling of the six. It pushed back ("I cannot confirm that profit declined overall in 2016"), gave the real monthly numbers, and said 2015 data would be needed to compare. No made-up answer. |
| 6 | Scatter of "employee salary" vs profit (no such column) | viz | The chart engine actually plotted `Sales` vs `Profit` (the saved file is titled "Sales versus Profit per Order"), but the narration kept calling it "Employee Salary vs Profit" and made up a "Salary range: $14.62 to $957.58". Reported as a success. |

Things worth knowing:

- The main problem is upstream, not in the Report Agent: the Data Query
  and Analysis planners quietly swap `sales` in for a missing column
  (Q3 and Q6 both did this). The Report Agent mostly just repeats what
  it's given.
- The Report Agent is actually more grounded than the narration. For Q6
  it used the structured chart data (labelled Sales/Profit) and so
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

## 5. Cross-model robustness (Ollama, Groq, Anthropic)

The system was run on three providers during the project. Anthropic
(Claude Haiku 4.5) is the only one with the full set of measurements
after the fixes, and is the main dataset (§2). Groq and Ollama were run
earlier and only partly. The tables below cover all three providers; a
dash (—) means that number was never measured, or was measured under
conditions that don't match the Anthropic run and so is left out. It
never means zero. §5.1 explains each gap.

### 5.1 What was evaluated on each provider

| Dimension | Ollama (`llama3.1:8b`, local) | Groq (`llama-3.3-70b-versatile`) | Anthropic (`claude-haiku-4-5`) |
|---|---|---|---|
| Correctness — real agents, Data Query + Visualization | ✅ | ✅ | ✅ |
| Correctness — real agents, Analysis | — | — | ✅ |
| Correctness — baseline, Data Query + Visualization | ✅ | ✅ | ✅ |
| Correctness — baseline, Analysis | — | — | ✅ |
| Correctness — monolithic agent | — | — | ✅ |
| Routing accuracy — overall | — | — | ✅ |
| Routing accuracy — per category | — | — | ✅ |
| Latency | — | — | ✅ |
| Per-difficulty breakdown | — | — | ✅ |
| Retry rate | ✅ | ✅ | ✅ |
| Report Agent — sessions 1–5 | — | — | ✅ |
| Report Agent — session 6 (adversarial) | — | — | ✅ |

Why the gaps exist:

- **Analysis correctness for Groq/Ollama is left out.** Those runs came
  before the §3.2 fix (baseline Analysis scoring) and the §3.5 fix
  (`compute_ttest` plus a reworded Analysis question), so they're not
  comparable to the Anthropic numbers. Data Query and Visualization
  aren't affected by either fix, so those numbers are kept.
- **The Groq raw run is still in git history.** The full first Groq run
  (`llama-3.3-70b-versatile`), every per-question file with its SQL and
  answer, is in commit `354902e`; the Data Query and Visualization
  numbers in §5.2 were checked against it. The Ollama run was overwritten
  before it got committed, so only its overall numbers survive (in the
  development log); the per-question files are gone.
- **The monolithic agent** was added after the Groq and Ollama runs and
  only ever run on Anthropic, so there's no decomposition value for the
  other two.
- **Latency, per-difficulty, and per-category routing** weren't saved for
  the Groq/Ollama runs.
- **Groq's routing number** is from the first run, before a routing bug
  was fixed in the restructure, so it's not comparable and is left out.
  **Ollama routing** never got a single number - the 8B model misroutes
  even clear questions (§5.4), and that run also ran into WSL memory
  limits.
- **The Report Agent** was only run on Anthropic.
- **Re-run after the fixes** (§5.7): only Anthropic was re-run. Groq
  removed the model, so re-running the same one isn't possible.

### 5.2 Correctness across providers

Groq and Ollama columns show only the categories measured under the same
(post-fix) conditions as Anthropic — Analysis is excluded for them (see
§5.1).

| | Ollama (8B) | Groq (Llama-3.3-70B) | Anthropic (Haiku 4.5) |
|---|---|---|---|
| **Real system** — Data Query | 90.0% | 100% | 93.3% |
| **Real system** — Analysis | — | — | 100% |
| **Real system** — Visualization | 80.0% | 100% | 90.0% |
| **Baseline** — Data Query | 30.0% | 33.3% | 76.7% |
| **Baseline** — Analysis | — | — | 40.0% |
| **Baseline** — Visualization | 70.0% | 80.0% | 50.0% |
| **Monolithic** — Data Query | — | — | 90.0% |
| **Monolithic** — Analysis | — | — | 80.0% |
| **Monolithic** — Visualization | — | — | 100% |

The pattern that holds on all three providers, for the two directly
comparable categories: **the real specialized system stays in an
80–100% correctness band regardless of the underlying model, while the
baseline swings much more widely (30–80%)**.

### 5.3 Architecture value and decomposition value

| | Ollama (8B) | Groq (Llama-3.3-70B) | Anthropic (Haiku 4.5) |
|---|---|---|---|
| Architecture value — Data Query | +60.0pp | +66.7pp | +16.7pp |
| Architecture value — Analysis | — | — | +60.0pp |
| Architecture value — Visualization | +10.0pp | +20.0pp | +40.0pp |
| Decomposition value — Data Query | — | — | +3.3pp |
| Decomposition value — Analysis | — | — | +20.0pp |
| Decomposition value — Visualization | — | — | -10.0pp |

Architecture value = real system minus baseline. Decomposition value =
real system minus monolithic, which needs the monolithic run (Anthropic
only). The -10.0pp Visualization decomposition value is explained
entirely by a single ambiguous question (§3.3).

### 5.4 Routing, latency, retry

| | Ollama (8B) | Groq (Llama-3.3-70B) | Anthropic (Haiku 4.5) |
|---|---|---|---|
| Routing accuracy — overall | — | — | 90.9% (50/55) |
| Routing accuracy — Data Query | — | — | 100% |
| Routing accuracy — Analysis | — | — | 66.7% |
| Routing accuracy — Visualization | — | — | 100% |
| Retry rate | 0% | 0% | 0% |
| Agent-only latency — DQ / An / Viz | — | — | 1.12 / 1.37 / 1.71 s |
| Full-pipeline latency — DQ / An / Viz | — | — | 3.50 / 3.82 / 4.94 s |
| Baseline latency — DQ / An / Viz | — | — | 1.08 / 5.09 / 1.63 s |
| Monolithic latency — DQ / An / Viz | — | — | 1.13 / 1.37 / 1.64 s |

Routing, latency and per-difficulty were only ever recorded for
Anthropic. Groq's routing was measured once in the first evaluation
round but before the routing-bug fix in the architecture restructure, so
it is not comparable and is not carried forward.

**Retry rate was 0% on all three providers** — the self-correcting loop
was never triggered by the 55-question benchmark on any model. (It was
first triggered by the adversarial Report-Agent session, §4.2, on
Anthropic, and did not recover.)

### 5.5 Per-difficulty correctness

| | Ollama | Groq | Anthropic — system | Anthropic — baseline |
|---|---|---|---|---|
| Data Query — easy / medium / hard | — | — | 90 / 90 / 100% | 70 / 80 / 80% |
| Analysis — easy / medium / hard | — | — | 100 / 100 / 100% | 33 / 67 / 17% |
| Visualization — easy / medium / hard | — | — | 100 / 100 / 67% | 67 / 75 / 0% |

### 5.6 Report Agent quality across providers

| | Ollama | Groq | Anthropic |
|---|---|---|---|
| Sessions 1–5 — mean Accuracy / Completeness / No-fabrication / Fluency | — | — | 4.0 / 5.0 / 4.0 / 5.0 |
| Session 6 (adversarial) — No-fabrication / Failure-transparency / Completeness / Fluency | — | — | 2 / 3 / 4 / 5 |

Full session-by-session ratings and the adversarial analysis are in §4.
Not run on Groq or Ollama.

### 5.7 Attempted post-fix re-run of Groq and Ollama

A re-run of the full evaluation on the other two providers was attempted,
to close the gaps above, and could not be completed:

- **Groq:** `llama-3.3-70b-versatile` has been retired by the provider
  and now returns `model_not_found`; the current Groq roster contains no
  Llama model. The nearest substitute, `openai/gpt-oss-120b`, runs the
  system correctly end-to-end, but Groq's free-tier limit of 8,000
  tokens per minute makes a full run (correctness + pipeline + report
  sessions, on the order of 1–2M tokens) impractical — the monolithic
  agent's large combined prompt saturates the limit and the run stalls
  on rate-limit backoff. A paid tier would remove this constraint.
- **Ollama:** `llama3.1:8b` is intact and a re-run is technically
  possible, but at 25–210 s per end-to-end question the full run is a
  multi-hour job on the same hardware that previously hit memory limits.
  Not completed.

The Ollama 8B model also showed, in the original run, a genuine routing
weakness (misrouting questions the hosted models route correctly) on top
of the infrastructure limits.

**For the Limitations section:** the cross-provider comparison is
strongest for **Data Query and Visualization correctness** (directly
comparable across all three providers) and for the **architecture-vs-
baseline pattern** (holds on all three). It is **Anthropic-only** for
decomposition value, latency, per-category routing, per-difficulty
breakdown, and Report-Agent quality.

---

## 6. What this evaluation does and does not establish — for the Limitations section

**Established, with evidence:**
- The specialized multi-agent architecture outperforms a minimal
  no-tools baseline, substantially and consistently. On Anthropic this
  holds across all three categories; on Groq and Ollama it is confirmed
  for the two categories measured under comparable conditions (Data
  Query and Visualization — §5.2).
- The architecture also outperforms a monolithic agent with identical
  tools and prompts (decomposition value: Data Query +3.3pp, Analysis +20.0pp,
  Visualization -10.0pp — the last explained entirely by a single
  ambiguous question, §3.3). Measured on Anthropic only — the monolithic
  baseline was added after the Groq/Ollama runs (§5.1).
- **A real correctness bug (`compute_ttest`) and a real evaluation
  scoring limitation were found, fixed, and the fix independently
  verified at three levels** (unit test, integration test against real
  ground truth, and a re-generated Report Agent session), a concrete
  demonstration of the evaluation process finding and correcting real
  issues, not just producing a number.
- Routing errors are concentrated at capability boundaries
  (Data Query/Analysis overlap for simple aggregates), not distributed
  randomly.
- The system's correctness is more stable across model choice than the
  baseline's (pattern confirmed pre- and post-fix).

**Not established, and should be stated as open questions:**
- Retry/self-correction effectiveness: first exercised by the adversarial
  session (§4.2), where the loop fired (`attempts: 3`) on two turns but
  could not recover because the fault was a missing column, not a
  correctable syntax error. The **first successful** self-correction in
  the whole evaluation was in the Catalan run (§7.3): one Analysis plan
  failed to parse, retried, and the second attempt scored correct. Still
  only two data points; the English 55-question benchmark showed a 0%
  retry rate.
- Cost comparison across providers, not systematically measured.
- Whether decomposition value would hold at a larger question count.
- **A full cross-provider re-run after the §3.2/§3.5 fixes.** Only
  Anthropic has post-fix Analysis data; for Groq and Ollama the Analysis
  category is excluded as non-comparable (§5.1), and their monolithic /
  latency / per-category-routing / Report-Agent cells were never filled.
  A post-fix re-run was attempted and blocked — Groq retired the model,
  Ollama is too slow on the available hardware (§5.7).
- **Decomposition value on Groq and Ollama** — the monolithic baseline
  was only ever run on Anthropic, so decomposition value is
  single-provider.
- **The multilingual evaluation (§7) is Anthropic Haiku only.** Spanish
  and Catalan were not run on Groq or Ollama, for the same reasons as
  §5.7 (Groq model retired; Ollama too slow) — those columns in §7 are
  blank.

---

## 7. Multilingual evaluation (Spanish and Catalan)

The evaluation was run again with the 55 questions and the 6 Report-Agent
sessions translated into Spanish and Catalan, to see if the language of
the question changes anything. This was only done on the main model
(Anthropic Claude Haiku 4.5). Groq and Ollama were not run in Spanish or
Catalan (§5.7), so their columns below are empty.

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

| | EN | ES | CA | Groq | Ollama |
|---|---|---|---|---|---|
| **Real system** — Data Query | 93.3% | 93.3% | 100% | — | — |
| **Real system** — Analysis | 100% | 100% | 100% | — | — |
| **Real system** — Visualization | 90.0% | 90.0% | 90.0% | — | — |
| **Baseline** — Data Query | 76.7% | 73.3% | 76.7% | — | — |
| **Baseline** — Analysis | 40.0% | 40.0% | 40.0% | — | — |
| **Baseline** — Visualization | 50.0% | 60.0% | 60.0% | — | — |
| **Monolithic** — Data Query | 90.0% | 86.7% | 93.3% | — | — |
| **Monolithic** — Analysis | 80.0% | 93.3% | 86.7% | — | — |
| **Monolithic** — Visualization | 100% | 90.0% | 90.0% | — | — |

The real system does about the same in all three languages. Real-system
correctness stays between 90% and 100% everywhere. The small changes
(Data Query 93.3 to 100 in Catalan, monolithic Analysis 80 to 93.3 in
Spanish) are caused by the two known ambiguities in §7.4, not by the
model being worse or better at a language. The baseline also fails on the
same questions in every language (see §7.4).

### 7.3 Routing, latency, retry by language

| | EN | ES | CA | Groq | Ollama |
|---|---|---|---|---|---|
| Routing accuracy — overall | 90.9% | 92.7% | 90.9% | — | — |
| Routing accuracy — Data Query | 100% | 100% | 96.7% | — | — |
| Routing accuracy — Analysis | 66.7% | 73.3% | 73.3% | — | — |
| Routing accuracy — Visualization | 100% | 100% | 100% | — | — |
| Agent-only latency — DQ / An / Viz (s) | 1.12 / 1.37 / 1.71 | 1.05 / 1.17 / 1.71 | 1.02 / 1.33 / 1.71 | — | — |
| Full-pipeline latency — DQ / An / Viz (s) | 3.50 / 3.82 / 4.94 | 3.18 / 4.15 / 5.36 | 3.12 / 4.18 / 5.48 | — | — |
| Retry rate | 0% | 0% | 6.7% (Analysis) | — | — |

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
two ambiguities already described in §3 - none of them is the model
misunderstanding Spanish or Catalan:

- **The order-counting ambiguity (§3.1).** For "how many orders", "orders
  by Second Class", "category with the most orders", "order count by
  segment", the agent uses `COUNT(DISTINCT order_id)` (5,009 orders,
  which §3.1 argues is the sensible reading) while the ground truth uses
  `COUNT(*)` (9,994 line items), or the other way round. Which one it
  picks changes with the language and the run: English and Spanish are
  marked wrong on "how many orders" (they chose DISTINCT), Catalan
  matches the ground truth there; the "order count by segment" chart
  flips the other way (English matches, Spanish and Catalan don't). These
  are scoring mismatches on an ambiguous question, not real mistakes.
- **The chart granularity ambiguity (§3.3).** The "profit over time, East
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

| | EN | ES | CA |
|---|---|---|---|
| Sessions 1–5 mean — Accuracy / Completeness / No-fabrication / Fluency | 4.0 / 5.0 / 3.8 / 5.0 | 4.2 / 5.0 / 3.8 / 5.0 | 3.8 / 5.0 / 3.4 / 5.0 |
| Session 6 (adversarial) — No-fab / Failure-transparency / Completeness / Fluency | 2 / 3 / 4 / 5 | 3 / 3 / 5 / 5 | 3 / 3 / 5 / 5 |

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
  ambiguities from the English analysis, or a normal baseline limit.
- The one gap is the output: the Report Agent always writes English, even
  when the conversation was in another language. A one-line prompt change
  would fix it; left as future work.
- This was one model (Anthropic Haiku) and one set of translations, done
  by me and not checked by anyone else.
