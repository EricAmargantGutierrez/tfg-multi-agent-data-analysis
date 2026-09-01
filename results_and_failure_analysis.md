# Evaluation Results and Failure Analysis

## 1. Methodology recap

The system was evaluated along four independent dimensions, each isolating a
different question:

1. **Correctness** — real specialized agents vs. two baselines, per
   category (SQL, Analysis, Visualization), against ground truth computed
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
4. **Report Agent quality** — qualitative only, by design: a session
   summary has no single ground truth, so this was rated by hand
   (accuracy, completeness, fabrication, fluency) rather than scored
   automatically.

All comparisons use structured output (rows, statistics results), never
narrated prose, which can phrase an identical correct answer many
different ways. The baseline uses a deliberately minimal, generic
prompt, not the specialized agents' tuned prompts, to isolate the value
of the architecture as a whole; the monolithic agent uses the *same*
tuned prompts as the real agents, to isolate decomposition specifically.

The benchmark (55 questions: 30 SQL, 15 Analysis, 10 Visualization,
stratified easy/medium/hard) was run against three different model
providers over the course of this evaluation. **The Anthropic run
(`claude-haiku-4.5`) is the primary, complete dataset reported below**,
including two corrections made after the initial full run, see §3.5 and
§3.2 for what changed and why.

---

## 2. Primary results (Anthropic, Claude Haiku 4.5) — current, post-fix

### 2.1 Correctness

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% (28/30) | 76.7% (23/30) | 90.0% (27/30) | +16.7pp | +3.3pp |
| Analysis | 100% (15/15) | 40.0% (6/15) | 80.0% (12/15) | +60.0pp | +20.0pp |
| Visualization | 90.0% (9/10) | 50.0% (5/10) | 100% (10/10) | +40.0pp | -10.0pp |

**Analysis numbers changed from the initial run** (baseline was 20.0%,
monolithic 86.7%, architecture value +80.0pp) after two corrections:
fixing a real bug in `compute_ttest` (§3.5) and a real limitation in this
evaluation's own scoring logic (§3.2). Both are described in detail
below, with before/after evidence, not just a note that a number moved.

### 2.2 Routing accuracy

**90.9% overall** (50/55). Per category: SQL 100%, Visualization 100%,
Analysis 66.7%. Unaffected by the fixes above (routing behavior didn't
change; only how correctness is scored and computed did).

### 2.3 Latency

| Category | Agent-only | Full pipeline | Baseline | Monolithic |
|---|---|---|---|---|
| SQL | 1.117s | 3.500s | 1.078s | 1.127s |
| Analysis | 1.367s | 3.817s | 5.086s | 1.366s |
| Visualization | 1.710s | 4.940s | 1.628s | 1.640s |

The baseline's Analysis latency (5.086s) is notably higher than every
other cell in this table, consistent with §3.5's finding that it now
attempts a genuinely more sophisticated manual SQL computation (per-group
mean, count, min, max, and a manually-derived standard deviation via a
correlated subquery) rather than a short, simple query.

### 2.4 Retry / self-correction

**Retry rate: 0% in every category**, unchanged by the fixes.

---

## 3. Failure analysis

### 3.1 The "how many orders" ambiguity — unchanged from the initial run

`COUNT(order_id)` (9,994 — line-item rows) vs. `COUNT(DISTINCT
order_id)` (5,009 — order transactions). Claude consistently applies the
DISTINCT interpretation everywhere "orders" is counted, including
changing the winning entity on "which customer placed the most orders"
("Emily Phan" under DISTINCT vs. "William Brown" under the ground
truth's convention). Not affected by the fixes in this section; retained
from the original failure analysis.

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

### 3.3 The chart time-granularity ambiguity — unchanged from the initial run

"Line chart of profit over time for the East region in 2017" never
specifies granularity. Three independent systems chose daily; only
ground truth assumed monthly. Explains the -10pp "decomposition value"
in Visualization at n=10. Not affected by this section's fixes.

### 3.4 Routing errors — unchanged from the initial run

4 of 5 routing misses are mean/average/median questions sent to SQL
instead of Analysis, a genuine SQL/Analysis boundary ambiguity, not
random noise. Unaffected by the fixes here.

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

### 3.6 Format-only misses and the row-cap ordering limitation — unchanged from the initial run

`SELECT *` instead of requested columns; pre-binned histograms as an
alternative (not wrong) representation; the `MAX_ROWS` + `ORDER BY`
interaction affecting which rows get returned when a result exceeds the
cap. See the original analysis for full detail — none of these are
affected by this section's fixes.

---

## 4. Report Agent — qualitative results (Session 5 re-rated after the fix)

| Session | Accuracy | Completeness | No fabrication | Fluency |
|---|---|---|---|---|
| 1 — SQL, easy | 3/5 | 5/5 | 2/5 | 5/5 |
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

Sessions 1, 2, and 4 are unaffected by this round of fixes and retain
their original ratings and issues (an invented, unrequested profit-margin
statistic in Session 1; small arithmetic errors and a cross-turn
misattribution in Session 4), see the original failure analysis for
full detail on those.

---

## 5. Cross-model robustness (Groq, Ollama, Anthropic)

**Caveat on this section after the fixes**: the Groq and Ollama
correctness data below predate both fixes in §3.2 and §3.5, they were
run against the old column-vs-column `compute_ttest` and the old,
overly conservative baseline scorer. The cross-provider *pattern*
(architecture stable, baseline variable) still holds and is worth
citing, but the exact Analysis percentages for Groq/Ollama are not
directly comparable to the corrected Anthropic figures above. A full
re-run on all three providers was not repeated, given the cost/time
already invested, worth flagging explicitly as a limitation rather than
implying a false apples-to-apples comparison.

### 5.1 The architecture is stable across models; the baseline is not

| | Ollama (8B, local) | Groq (70B, hosted) | Anthropic (Haiku 4.5, post-fix) |
|---|---|---|---|
| Real system — SQL | 90% | 100% | 93.3% |
| Real system — Analysis | 100% | 100% | 100% |
| Real system — Visualization | 80% | 100% | 90.0% |
| Baseline — SQL | 30% | 33.3% | 76.7% |
| Baseline — Analysis | 26.7%* | 20-26.7%* | 40.0% |
| Baseline — Visualization | 70% | 80% | 50.0% |

\* Pre-fix figures — see caveat above.

The real, specialized-agent system stays in an 80-100% band regardless
of the underlying model; the baseline swings more widely. This pattern
is unaffected by the fixes (they changed how correctly the baseline's
*existing* answers were scored, not the system's own behavior).

### 5.2 Retry rate and the Ollama infrastructure findings — unchanged

See the original analysis: 0% retry rate across all three providers; the
Ollama run's genuine model-level routing weakness and the local
memory/thermal infrastructure issues, both unaffected by this round of
fixes.

---

## 6. What this evaluation does and does not establish — for the Limitations section

**Established, with evidence:**
- The specialized multi-agent architecture outperforms a minimal
  no-tools baseline, substantially and consistently, across three
  different model providers.
- The architecture also outperforms a monolithic agent with identical
  tools and prompts (decomposition value: SQL +3.3pp, Analysis +20.0pp,
  Visualization -10.0pp — the last explained entirely by a single
  ambiguous question, §3.3).
- **A real correctness bug (`compute_ttest`) and a real evaluation
  scoring limitation were found, fixed, and the fix independently
  verified at three levels** (unit test, integration test against real
  ground truth, and a re-generated Report Agent session), a concrete
  demonstration of the evaluation process finding and correcting real
  issues, not just producing a number.
- Routing errors are concentrated at capability boundaries
  (SQL/Analysis overlap for simple aggregates), not distributed
  randomly.
- The system's correctness is more stable across model choice than the
  baseline's (pattern confirmed pre- and post-fix).

**Not established, and should be stated as open questions:**
- Retry/self-correction effectiveness, never empirically exercised.
- Cost comparison across providers, not systematically measured.
- Whether decomposition value would hold at a larger question count.
- **A full cross-provider re-run after the §3.2/§3.5 fixes**, only
  Anthropic was re-run; Groq and Ollama's Analysis figures reflect the
  pre-fix system and scorer.
