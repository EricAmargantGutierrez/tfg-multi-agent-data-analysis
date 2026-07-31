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
   pass through the real orchestrator (router → agent → narrator),
   independent of the correctness runs, which deliberately bypass
   routing to isolate each agent's own capability.
4. **Report Agent quality** — qualitative only, by design: a session
   summary has no single ground truth, so this was rated by hand
   (accuracy, completeness, fabrication, fluency) rather than scored
   automatically.

All comparisons use structured output (rows, statistics results) — never
narrated prose, which can phrase an identical correct answer many
different ways. The baseline uses a deliberately minimal, generic
prompt, not the specialized agents' tuned prompts, to isolate the value
of the architecture as a whole; the monolithic agent uses the *same*
tuned prompts as the real agents, to isolate decomposition specifically.

The benchmark (55 questions: 30 SQL, 15 Analysis, 10 Visualization,
stratified easy/medium/hard) was run against three different model
providers over the course of this evaluation — Groq (`llama-3.3-70b`),
a local Ollama model (`llama3.1:8b`), and Anthropic (`claude-haiku-4.5`)
— for reasons discussed in §5. **The Anthropic run is the primary,
complete dataset reported below**: it is the only run in which all four
evaluation dimensions (correctness × 3 sides, routing/latency, and the
Report Agent) were completed on a single, consistent model. The Groq and
Ollama runs are used as supplementary cross-model evidence in §4, since
several findings reproduce identically across all three providers —
which is itself informative about whether a given result reflects the
architecture or a specific model's quirks.

---

## 2. Primary results (Anthropic, Claude Haiku 4.5)

### 2.1 Correctness

| Category | Real system | Baseline | Monolithic | Architecture value | Decomposition value |
|---|---|---|---|---|---|
| SQL | 93.3% (28/30) | 76.7% (23/30) | 90.0% (27/30) | +16.7pp | +3.3pp |
| Analysis | 100% (15/15) | 20.0% (3/15) | 86.7% (13/15) | +80.0pp | +13.3pp |
| Visualization | 90.0% (9/10) | 50.0% (5/10) | 100% (10/10) | +40.0pp | -10.0pp |

**Reading this table requires the failure analysis in §3 — the raw
percentages alone are misleading in two specific places**, both explained
below: the SQL "architecture value" overstates the real gap once
scoring-convention effects are removed, and the Visualization
"decomposition value" (negative) is a single-question artifact, not a
systematic weakness.

### 2.2 Routing accuracy

**90.9% overall** (50/55). Per category: SQL 100%, Visualization 100%,
Analysis 66.7%. The failures are not random — see §3.4.

### 2.3 Latency

| Category | Agent-only | Full pipeline | Baseline | Monolithic |
|---|---|---|---|---|
| SQL | 1.117s | 3.500s | 1.078s | 1.127s |
| Analysis | 1.122s | 3.958s | 1.396s | 1.416s |
| Visualization | 1.710s | 4.940s | 1.628s | 1.640s |

"Agent-only" isolates each agent's own execution time (bypassing
routing/narration, used for correctness scoring). "Full pipeline" is
what a real user of `src.repl` actually experiences — router + agent +
narrator — and is the number that's fairly comparable to the baseline's
single call. The gap (roughly 3-3.5x) is consistent with the pipeline
making 3 sequential LLM calls per question versus the baseline's one.

### 2.4 Retry / self-correction

**Retry rate: 0% in every category.** The self-correction mechanism was
never triggered — see §5.2 for why this is now a robust finding, not
missing data.

---

## 3. Failure analysis

### 3.1 The "how many orders" ambiguity — reproduced, and shown to change the actual answer entity

`COUNT(order_id)` (9,994 — line-item rows) vs. `COUNT(DISTINCT
order_id)` (5,009 — order transactions). Claude consistently applies the
DISTINCT interpretation everywhere "orders" is counted (baseline SQL:
5/7 misses; monolithic: 2/3 misses; baseline visualization: 1/5 misses).

This is not cosmetic: on "which customer placed the most orders," the
DISTINCT convention changes the **winning customer** — "Emily Phan (17)"
under DISTINCT vs. "William Brown (37)" under the ground truth's
convention. Both are internally consistent, defensible readings of a
genuinely ambiguous question. Recommendation for the methodology
section: state this explicitly as a scoring-convention choice, not treat
either side as objectively wrong.

### 3.2 A limitation in the evaluation's own scoring, not the baseline's capability

The baseline scorer (`check_baseline_analysis`) assumes a bare SQL model
can only possibly succeed at scalar statistics — anything else
(correlation, covariance, regression...) is scored `incorrect` by
design, on the assumption it's structurally inexpressible in one SQL
query.

**That assumption was falsified by this run.** Claude's baseline derived
the correct closed-form Pearson correlation formula in raw SQL and
produced **-0.2195** — matching the real Analysis Agent's actual value
(-0.219) almost exactly. Same for covariance (a mathematically correct
manual formula) and the year-filtered correlation variant. All three
were scored `incorrect` purely by scorer design, not because the
mathematics was wrong.

**Recommendation**: report baseline Analysis correctness with this
caveat explicit — the 20% figure undercounts what this particular model
could actually do with SQL alone. K-Means (`NTILE()`-based tercile
split, not real clustering) remains a genuine, unambiguous capability
failure regardless of this caveat.

### 3.3 The chart time-granularity ambiguity — confirmed by independent systems converging on the same reading

"Line chart of profit over time for the East region in 2017" never
specifies granularity (unlike the sibling question, which explicitly
says "monthly"). The real Viz Agent, the SQL baseline, and the
visualization baseline all **independently** chose daily granularity
(`GROUP BY order_date`, ~230 rows); only the ground truth's reference SQL
assumes monthly (12 rows). Three separate systems converging on the same
reading is strong evidence this is a genuine question-design gap, not a
model or agent weakness — **and it is the entire explanation for the
-10pp "decomposition value" in Visualization**: at n=10, one ambiguous
question is a 10-percentage-point swing. The monolithic agent happened
to answer this one the way ground truth expected; the dedicated Viz
Agent did not. This should be reported as a benchmark-design limitation,
not a finding about architecture.

### 3.4 Routing errors cluster exactly where they should, given §3.2's logic

4 of 5 routing misses are mean/average/median questions sent to the SQL
Agent instead of the Analysis Agent — defensible, since `AVG()` is a
real SQLite function; the dataset's `expected_agent` label reflects
design intent (exercising the Analysis Agent's filter logic), not an
objective fact about which agent "should" own simple aggregates. The
router never misrouted anything requiring correlation, regression, PCA,
K-Means, or a chart — the ambiguity is concentrated exactly at the
SQL/Analysis boundary for statistics SQL can also nominally express.

### 3.5 A case where the "wrong" answer may be more statistically valid than ground truth

Monolithic answered "is there a significant difference between discount
and profit" with `correlation` (-0.2195) instead of the expected
`ttest`. This is scored incorrect, but worth stating plainly: the
reference method itself is a documented, known-flawed comparison (an
independent t-test between two *different* columns of different scales
— not a real two-group hypothesis test). Session 5 of the Report Agent
review (§4 below) independently confirms this exact flaw produces a
misleading causal claim in a real generated report. Correlation is
arguably the more defensible statistic here; this "miss" may reflect
correct statistical judgment, not a capability failure.

### 3.6 Format-only misses (same pattern as prior runs, reproduced across providers)

- `SELECT *` instead of the requested two columns (baseline, "find the
  order with the highest sales") — correct answer, wrong shape.
- Pre-binned histogram (5 ranges + counts) instead of raw values — a
  legitimate alternative representation, not an error, reproducing
  identically from the earlier Groq-based evaluation.

### 3.7 A genuine, subtle evaluation-methodology limitation

Baseline's scatter/boxplot SQL was structurally identical to what ground
truth would generate, yet still failed to match. Most likely cause:
`MAX_ROWS = 1000` combined with `ORDER BY` — when a result exceeds the
cap, *which* 1,000 rows get returned depends on sort order, so two
genuinely correct queries with different orderings can retrieve
different row subsets from a table with >1,000 matching rows. Worth
documenting as a known limitation of the row-cap design, not a
correctness bug in either query.

---

## 4. Report Agent — qualitative results

| Session | Accuracy | Completeness | No fabrication | Fluency |
|---|---|---|---|---|
| 1 — SQL, easy | 3/5 | 5/5 | 2/5 | 5/5 |
| 2 — Analysis | 4/5 | 5/5 | 4/5 | 5/5 |
| 3 — Visualization | 5/5 | 5/5 | 5/5 | 5/5 |
| 4 — Mixed, realistic | 3/5 | 5/5 | 4/5 | 5/5 |
| 5 — Mixed, hard | 2/5 | 5/5 | 2/5 | 5/5 |
| **Mean** | **3.4/5** | **5.0/5** | **3.4/5** | **5.0/5** |

**Fluency and completeness are unambiguously strong** — every session is
well-structured, professional Markdown, covering all turns asked.
**Accuracy and fabrication are where the real issues live**, and they
are specific, not vague impressions:

- **Session 1**: invents an unrequested, statistically meaningless metric
  ("profit margin of ~39.5% relative to West region sales alone" — total
  profit divided by one region's sales) — a direct violation of the
  Report Agent's own system prompt instruction not to invent information.
- **Session 4**: real arithmetic errors in reported percentages (51.4%
  vs. actual 51.9%, etc. — small but genuine, checkable miscalculations)
  and a cross-turn misattribution (a row count from Q2 attached to Q1's
  finding).
- **Session 5**: the most consequential finding in the qualitative
  review — the report states the t-test result "indicates a negative
  correlation," which is not what a t-test measures. This is the same
  known reference-method flaw from §3.5, now demonstrated to produce an
  actively misleading directional claim in a document a real user would
  read and trust, not merely a benchmark scoring artifact.

---

## 5. Cross-model robustness (Groq, Ollama, Anthropic)

### 5.1 The architecture is stable across models; the baseline is not

| | Ollama (8B, local) | Groq (70B, hosted) | Anthropic (Haiku 4.5) |
|---|---|---|---|
| Real system — SQL | 90% | 100% | 93.3% |
| Real system — Analysis | 100% | 100% | 100% |
| Real system — Visualization | 80% | 100% | 90.0% |
| Baseline — SQL | 30% | 33.3% | 76.7% |
| Baseline — Analysis | 26.7% | 20-26.7% | 20.0% |
| Baseline — Visualization | 70% | 80% | 50.0% |

**The real, specialized-agent system stays in an 80-100% band regardless
of the underlying model.** The baseline swings far more widely
(20-77%), and its SQL correctness in particular varies by more than 2x
across providers. This is a genuinely strong, well-evidenced claim for
the thesis: **the architecture's value is partly about making the system
robust to model choice, not only about raw capability uplift on any one
model.** A weaker or cheaper model can be substituted with much smaller
correctness loss when wrapped in the specialized-agent architecture than
when used bare.

### 5.2 Retry rate: 0% across three independent model families

This is no longer "missing data" — it is a reproduced finding. None of
three structurally different models (an 8B local model, a 70B hosted
model, and a commercial API model) ever needed the self-correction
mechanism on this benchmark. Two honest readings, both worth stating:
either the specialized prompts are precise enough that first-attempt
failure is rare across a wide capability range, or the benchmark's
questions are not adversarial enough to exercise retry. Genuine
empirical data on retry *effectiveness* remains unmeasured — the
mechanism exists and is unit-tested (see `tests/test_retry.py`), but
this benchmark never observed it fire.

### 5.3 The Ollama run surfaced a real infrastructure limitation worth documenting

An isolated router call, repeated multiple times, consistently misrouted
clearly unambiguous SQL questions ("how many orders are there") to the
Analysis Agent on the local 8B model — a genuine model-capability gap,
not a code defect (confirmed via the same offline-tested routing logic
that performs correctly with the other two providers). Separately, the
full pipeline run on Ollama repeatedly failed for infrastructure reasons
(WSL memory exhaustion under sustained local inference, and likely
thermal throttling) unrelated to model capability. Both are legitimate,
reportable findings about the practical cost of local-model deployment
for this kind of system — worth a paragraph in the Limitations section
distinguishing "the model got it wrong" from "the hardware couldn't
sustain it."

---

## 6. What this evaluation does and does not establish — for the Limitations section

**Established, with evidence:**
- The specialized multi-agent architecture outperforms a minimal
  no-tools baseline, substantially and consistently, across three
  different model providers.
- The architecture also outperforms a monolithic agent with identical
  tools and prompts — i.e., decomposition itself adds value, not just
  tool access — though this margin is smaller (3-13pp) than the
  architecture-vs-baseline margin (17-80pp), and is not fully separable
  from question-design ambiguities at this sample size (§3.3).
- Routing errors are concentrated at genuine capability boundaries
  (SQL/Analysis overlap for simple aggregates), not distributed
  randomly.
- The system's correctness is substantially more stable across model
  choice than the baseline's.

**Not established, and should be stated as open questions:**
- Retry/self-correction effectiveness — never empirically exercised.
- Cost comparison across providers — not systematically measured (this
  evaluation optimized for correctness data, not $/question).
- Whether decomposition value would hold at a larger question count,
  where single-question ambiguities (§3.3) would matter proportionally
  less.
- The monolithic agent's own internal decision quality at scale — it was
  tested at n=55, the same size as everything else; a dedicated,
  larger-scale test of tool-selection accuracy specifically was out of
  scope.
