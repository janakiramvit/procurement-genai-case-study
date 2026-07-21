# KPI Evidence Trail — Complete Audit

Every number in the P0 KPI scorecard, traced back to `eval/eval_results.json` (the 15-question
offline eval — q1 through q15) with the exact formula, raw inputs, and question-level
attribution shown. Nothing here is asserted without a reproducible calculation.

**Correction made during this audit:** the original scorecard's *Unsupported Question Rate*
(13.3%) used the eval set's *intended* out-of-scope questions (q12, q13) as the numerator. That
undercounts the metric it claims to measure — it should reflect what the system actually did,
which includes q7 (a policy question the router misrouted into a refusal). Corrected to **20%
(3/15)** below, and `kpi_scorecard.md` has been updated to match. Flagged rather than silently
fixed, since a reconciliation exercise that quietly changes its own prior numbers defeats the
point of the exercise.

**Classification key** (5 categories, stricter than the original scorecard's 3):
- **Measured** — a directly-logged value, read off with no formula beyond standard statistics (e.g. a percentile) applied to complete raw data.
- **Derived** — computed by an exact formula from other already-measured, complete counts. No sampling, no assumption, no stand-in concept.
- **Proxy** — the real KPI isn't observable (no production usage exists), so a different, measurable quantity from the eval set is used as a stand-in. Always a different concept, clearly named as such.
- **Estimated** — requires an assumption beyond counted data (token-size modeling, etc.). None of the 9 KPIs below are Estimated; flagged here only so the taxonomy is complete.
- **Not Yet Measured** — no defensible number, proxy or otherwise, exists from this eval. Explained, not filled in.

Full per-question raw data (query text, category routing, groundedness detail, relevance score,
latency) is in `eval/eval_results.json`; the relevant fields are quoted inline below rather than
reproducing the whole file.

---

## NORTH STAR

### 1. Procurement Self-Service Rate

1. **KPI:** Procurement Self-Service Rate
2. **Final value:** **69.2%**
3. **Classification:** Proxy — there is no production usage to measure a real self-service rate against; this substitutes "did the 15-question eval set resolve cleanly" for "do real users self-serve."
4. **Exact formula:** `(in-scope questions with a correctly-routed, groundedness-passed, non-escalated answer) ÷ (all in-scope questions)`
5. **Raw data used:** `expected_category`, `actual_category`, `category_match`, `groundedness[].passed`, and the literal `answer` text (checked for escalation language: "escalate", "couldn't verify", "couldn't reliably") for all 15 questions.
6. **Calculation steps:**
   - Step 1 — exclude questions where `expected_category == OUT_OF_SCOPE` (they test refusal, not self-service): removes q12, q13. Remaining: 13 questions.
   - Step 2 — of those 13, count questions where the router's `actual_category` matched `expected_category` AND every applicable `groundedness.passed == True` AND the answer text contains no escalation language: q3, q4, q5, q6, q8, q9, q10, q11, q15 = **9**.
   - Step 3 — 9 ÷ 13 = 0.6923 = **69.2%**.
7. **Contributing question IDs (numerator, clean self-service):** q3, q4, q5, q6, q8, q9, q10, q11, q15 (9)
   **Contributing question IDs (denominator, all in-scope):** q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q14, q15 (13)
8. **Excluded question IDs (and why):** q12, q13 — excluded from the denominator entirely. Both are deliberately-injected out-of-scope control questions; they test whether the system correctly *refuses*, which is a different capability than self-service resolution, and including them would inflate or deflate the rate based on an unrelated behavior.
9. **Assumptions:**
   - q1, q2, q14 (escalation language present) and q7 (misrouted to refusal) all count as "not self-served," with no partial credit — even though q1 and q14 did return a partial, useful data-path answer alongside the caveat. A stricter or looser credit rule would move this number; 69.2% is the strict reading (any caveat or misroute = not self-served).
   - The eval set (n=13 in-scope) is a hand-written, deliberately-hard set (see Assumption in Appendix A of `kpi_scorecard.md`), not a sample of real question frequency. This number describes *how the system behaves on this specific set*, not a population estimate.
10. **Interview explanation:** "On our 15-question test set, 9 of 13 in-scope questions got a complete answer with no caveat — a 69% clean self-service rate. The other 4 either got flagged for human review by our own QA gate, or in one case were incorrectly refused by the router. We don't have a real self-service rate yet because there's no production traffic — this number describes the prototype's behavior on a stress-test set, not real usage."

---

## COVERAGE

### 2. Unsupported Question Rate

1. **KPI:** Unsupported Question Rate
2. **Final value:** **20.0%** (corrected from the original scorecard's 13.3% — see note above)
3. **Classification:** Proxy — stands in for "how often would a real user be told the system can't help," using the eval set's mix as a substitute for a real query distribution.
4. **Exact formula:** `(questions where actual_category == OUT_OF_SCOPE) ÷ (all 15 questions)`
5. **Raw data used:** `actual_category` for all 15 questions.
6. **Calculation steps:**
   - Step 1 — count questions where `actual_category == "OUT_OF_SCOPE"`: q7, q12, q13 = 3.
   - Step 2 — 3 ÷ 15 = **20.0%**.
7. **Contributing question IDs:** q7, q12, q13 (3)
8. **Excluded question IDs (and why):** None excluded — this metric is defined over the full 15-question set by design, since it measures the system's overall refusal rate, not a rate conditional on scope.
9. **Assumptions:**
   - This treats q7 (a genuine policy question the router misrouted) identically to q12/q13 (genuinely off-topic questions), because from the *user's* point of view, all three produced the same refusal message. An alternative, narrower definition — "rate of questions the system was *designed* to refuse" — would use only q12/q13 and give 13.3%. That number describes eval-set design, not system behavior, which is why 20.0% is reported as the primary value here.
   - Both readings share the same limitation: 2 of the 15 questions were deliberately written to be off-topic, so this ratio reflects the eval author's choices, not a real question-arrival distribution.
10. **Interview explanation:** "3 of our 15 test questions got refused as out-of-scope — 20%. One of those three shouldn't have been refused at all; it was a legitimate policy question our router misclassified. So this 20% is really two different things bundled together: correct refusals and a router miss, and we track that distinction internally rather than let one number hide it."

### 3. Top Escalation Categories

1. **KPI:** Top Escalation Categories
2. **Final value:** 4 distinct root-cause categories (qualitative — sample too small to rank by frequency)
3. **Classification:** Proxy — stands in for a ranked, volume-based escalation taxonomy that would require real escalation logs; instead, every failure in the eval set is manually categorized by root cause.
4. **Exact formula:** None (qualitative classification, not a computed statistic). Method: every question with a failed groundedness check or a routing miss was read individually and assigned to a root-cause bucket.
5. **Raw data used:** `groundedness[].reasoning` (the LLM-judge's stated reason for failure) and `actual_category` for all questions with a failure.
6. **Calculation steps:**
   - Step 1 — identify every question with at least one `groundedness.passed == False`, or a `category_match == False` where the miss caused a refusal: q1, q2, q7, q14.
   - Step 2 — read each one's failure reasoning and assign a root cause:
     - q1 → source document itself contains an unresolved placeholder ("$[C]") the judge correctly refused to treat as a real number.
     - q2 → relevant content exists in the corpus, but wasn't retrieved in the top-6 chunks (a retrieval-recall gap, not a missing-content gap — confirmed by direct keyword search, documented in DESIGN.md).
     - q14 → the data half of a BOTH question succeeded; the policy half was judged ungrounded because the retrieved passages never mention DVBE at all.
     - q7 → the term (Leveraged Procurement Agreement) isn't documented anywhere in the KnowledgeBase, and the router defaulted to an out-of-scope refusal rather than routing to a policy search that would have honestly come up empty.
7. **Contributing question IDs:** q1, q2, q7, q14 (one per category, 1:1 in this small sample)
8. **Excluded question IDs (and why):** All others (q3, q4, q5, q6, q8, q9, q10, q11, q12, q13, q15) — these either passed cleanly or were correctly-refused controls, so there's no failure to categorize.
9. **Assumptions:**
   - With exactly one example per category, this cannot be presented as a ranked/weighted list ("category X accounts for N% of escalations") — that would imply a sample size this data doesn't have. It's presented as "these 4 distinct failure modes exist," not "these are the top 4 by volume."
   - Categorization is a judgment call made by reading the judge's `reasoning` text, not an automated classifier — a different reader might group q1 and q14 together (both are "policy leg failed within a BOTH question") rather than treating q1 as a placeholder-specific issue. Both groupings are defensible; the 4-category version separates by root cause rather than by symptom.
10. **Interview explanation:** "In our 15-question set, every escalation traced to one of four distinct causes — an incomplete source document, a retrieval gap on content that does exist, a mixed-category question where only half the answer was grounded, and a term that isn't in our corpus at all. Four different problems means four different fixes, which is exactly why we didn't roll this into one 'groundedness failure' bucket."

---

## TRUST

### 4. Answer Accuracy

1. **KPI:** Answer Accuracy
2. **Final value:** **Cannot be computed from this evaluation.**
3. **Classification:** Not Yet Measured
4. **Exact formula:** N/A
5. **Raw data used:** N/A
6. **Calculation steps:** N/A
7. **Contributing question IDs:** None
8. **Excluded question IDs (and why):** All 15 — none of them have an independently-verified "correct answer" label attached. `eval_questions.json` records an `expected_category` and, for policy questions, an `expected_source` (which document *should* be cited) — neither is a ground-truth answer to check the generated text against.
9. **Assumptions:** None made — this is deliberately left blank rather than backfilled with a proxy, because the two closest available numbers (Grounded Response Rate, Relevance Score) measure different things and conflating either with "accuracy" would overstate confidence:
   - Grounded Response Rate confirms an answer is *supported by its cited source* — not that the source (or the answer) is factually correct about the real world.
   - Relevance Score confirms an answer *addresses the question asked* — not that it's correct.
   - A true Answer Accuracy metric requires a human subject-matter expert to grade each answer against a real, independently-verified correct answer. That grading has not been done for any of the 15 questions.
10. **Interview explanation:** "We don't have an accuracy number, and I'm not going to back into one from groundedness or relevance, because both measure something adjacent, not accuracy itself. Building this requires a small gold-standard answer set graded by a procurement SME — that's a specific, scoped P1 task, not a gap I'd paper over with today's data."

### 5. Grounded Response Rate

1. **KPI:** Grounded Response Rate
2. **Final value:** **78.6%**
3. **Classification:** Derived — an exact combination of two already-measured, complete counts (policy and data groundedness pass rates), via simple arithmetic. Not a proxy for a different concept; it is precisely what it claims to be.
4. **Exact formula:** `(policy checks passed + data checks passed) ÷ (policy checks attempted + data checks attempted)`
5. **Raw data used:** every `groundedness` entry (each has `path`: "policy" or "data", and `passed`: true/false) across all 15 questions.
6. **Calculation steps:**
   - Step 1 — list every groundedness check with `path == "policy"`: q1(False), q2(False), q6(True), q8(True), q11(True), q14(False), q15(True) → 7 attempts, 4 passed.
   - Step 2 — list every groundedness check with `path == "data"`: q1(True), q3(True), q4(True), q5(True), q9(True), q10(True), q14(True) → 7 attempts, 7 passed.
   - Step 3 — (4 + 7) ÷ (7 + 7) = 11 ÷ 14 = 0.7857 = **78.6%**.
7. **Contributing question IDs:** Policy checks: q1, q2, q6, q8, q11, q14, q15 (7). Data checks: q1, q3, q4, q5, q9, q10, q14 (7). Note q1 and q14 each contribute *two* checks (one policy, one data) since they were routed to BOTH.
8. **Excluded question IDs (and why):** q7, q12, q13 — no groundedness check was ever run for these, because the router classified all three as OUT_OF_SCOPE, which short-circuits the pipeline before either agent (and therefore either QA check) executes. There is nothing to include or exclude a verdict for; the check never happened.
9. **Assumptions:**
   - Policy and data checks are weighted equally in this blend (each of the 14 checks counts once), not weighted by question. A question routed to BOTH (q1, q14) contributes two checks to this metric, effectively counting twice — a deliberate choice, since the metric is about check-level groundedness, not question-level.
   - Policy groundedness (LLM-judge, probabilistic) and data groundedness (deterministic, execution-success only) are fundamentally different kinds of checks — see DESIGN.md §4 for why they use different mechanisms. Blending them into one percentage is a simplification useful for an executive summary; the two components (57.1% vs. 100%) are more informative individually and are reported separately elsewhere in the scorecard.
10. **Interview explanation:** "78.6% of every groundedness check we ran — 11 of 14 — passed. That splits into two very different stories: our SQL answers are grounded 100% of the time because we can verify execution directly, while our policy answers pass 57% of the time because verifying free-text groundedness is inherently harder and probabilistic. The blended number is useful for a one-line summary; the split is what we actually act on."

### 6. Hallucination Rate

1. **KPI:** Hallucination Rate
2. **Final value:** **Not measured.** Related, bounded figure available: 21.4% of attempted answers were suppressed by the QA gate before reaching the user (the complement of Grounded Response Rate) — this is a different quantity, not the hallucination rate itself.
3. **Classification:** Not Yet Measured
4. **Exact formula:** N/A for the KPI itself. The bounded complement figure: `1 − (Grounded Response Rate) = 1 − 0.786 = 0.214`
5. **Raw data used (for the bounded complement only):** the same 14 groundedness checks used in KPI #5.
6. **Calculation steps (bounded complement only):** 14 total checks − 11 passed = 3 failed → 3 ÷ 14 = 21.4%.
7. **Contributing question IDs (bounded complement):** the 3 failed checks — q2(policy), q7 n/a (never checked, see below), q14(policy). Correction: q7 had no groundedness check (router misroute, excluded per KPI #5's rule) — the 3 failures are q1(policy), q2(policy), q14(policy). All 3 data checks passed; all failures are on the policy side.
8. **Excluded question IDs (and why):** q7, q12, q13 — same reason as KPI #5: no groundedness check ran, so there's no pass/fail signal to include.
9. **Assumptions:**
   - The 21.4% figure measures answers *caught and suppressed* by the QA gate — it is explicitly not the rate of hallucinations that reached the end user, which is the actual definition of Hallucination Rate. Every one of those 3 failed-check answers was replaced with the safe fallback message before being shown, by design (see `orchestrator.py` lines 102-119).
   - Whether *zero* hallucinations reached users, or some non-zero number slipped past both the LLM-judge and the deterministic check, has not been tested. No adversarial/red-team attempt to induce a hallucination that passes QA has been run against this system.
   - Measuring a true Hallucination Rate requires either (a) a red-team exercise designed to find QA-gate blind spots, or (b) production traffic reviewed by a human for any answer that passed QA but was still wrong.
10. **Interview explanation:** "We don't have a hallucination rate, and I want to be precise about why: we know 21% of attempted answers were caught and blocked by our QA gate before the user ever saw them — that's a real, measured number, but it's 'how often did our safety net catch something,' not 'how often did something slip through.' We haven't red-teamed this system to find out if the net has holes, and I'd rather say that plainly than quote a 0% hallucination rate we haven't actually tested for."

---

## EFFICIENCY

### 7. Average Response Time

1. **KPI:** Average Response Time
2. **Final value:** **p50 = 3,636 ms, p95 = 6,830 ms**
3. **Classification:** Measured — every value is a directly-logged wall-clock duration for a real pipeline execution; p50/p95 are standard percentile statistics over complete, un-sampled data (all 15 runs), not a model or a proxy.
4. **Exact formula:** `p50 = median(latencies)`; `p95 = sorted(latencies)[round(0.95 × n) − 1]` where n = 15 (exact code from `scripts/evaluate.py::summarize`)
5. **Raw data used:** `total_latency_ms` for every question: q1=7420, q2=5969, q3=2438, q4=3636, q5=2766, q6=6830, q7=1012, q8=4593, q9=3275, q10=2466, q11=3769, q12=910, q13=924, q14=5982, q15=4094.
6. **Calculation steps:**
   - Step 1 — sort all 15 latencies: 910, 924, 1012, 2438, 2466, 2766, 3275, 3636, 3769, 4094, 4593, 5969, 5982, 6830, 7420.
   - Step 2 — p50 = median of 15 values = the 8th value = **3,636 ms** (independently reproduced with Python's `statistics.median` during this audit — matches exactly).
   - Step 3 — p95 index = `round(0.95 × 15) − 1 = round(14.25) − 1 = 14 − 1 = 13` (0-indexed) → the 14th sorted value = **6,830 ms** (independently reproduced — matches exactly).
7. **Contributing question IDs:** all 15 (q1–q15) — latency is captured for every request regardless of category, routing correctness, or QA outcome.
8. **Excluded question IDs (and why):** None. Latency is a property of pipeline execution, not answer quality, so there is no principled reason to exclude any question.
9. **Assumptions:**
   - n=15 is a small sample for a p95 statistic — the "95th percentile" of 15 points is really just "the 2nd-slowest value," which is far less statistically stable than a p95 computed over thousands of real requests. This number characterizes the eval run, not a production-grade latency SLA.
   - Latency includes every LLM call in the pipeline (router + retrieval/generation + QA + synthesizer where applicable), so BOTH-category questions with a synthesizer call are structurally slower than single-path questions — q1 (7,420 ms, BOTH) and q6 (6,830 ms, POLICY only) are the two slowest, and q6's outlier latency isn't explained by category alone.
10. **Interview explanation:** "Half our test questions answer in 3.6 seconds or less; the slowest ran in 6.8 seconds. That's end-to-end, including every verification step — we're not hiding QA cost from the latency number. With only 15 samples this isn't a production SLA yet, but it tells us the multi-agent overhead is in the single-digit-seconds range, not minutes."

### 8. SME Escalation Rate

1. **KPI:** SME Escalation Rate
2. **Final value:** **23.1%** (3 of 13 in-scope questions). A broader reading that also counts the router-misclassification failure gives **30.8%** (4 of 13) — see Assumptions for why 23.1% is the primary figure.
3. **Classification:** Proxy — stands in for a real production escalation rate, which requires actual escalation events (none exist; there's no escalation integration at all — see KPI #9).
4. **Exact formula:** `(in-scope questions whose answer text contains explicit escalation language) ÷ (all in-scope questions)`
5. **Raw data used:** `expected_category` (to define the in-scope denominator) and the literal `answer` text for all 15 questions.
6. **Calculation steps:**
   - Step 1 — denominator: in-scope questions = all except q12, q13 (see KPI #1, Step 1) = 13.
   - Step 2 — numerator: questions whose `answer` text explicitly recommends escalation ("I couldn't verify... escalate to L2," or the appended caveat "please verify separately or escalate to L2"): q1, q2, q14 = 3.
   - Step 3 — 3 ÷ 13 = **23.1%**.
7. **Contributing question IDs (numerator):** q1, q2, q14 (3)
   **Contributing question IDs (denominator):** q1, q2, q3, q4, q5, q6, q7, q8, q9, q10, q11, q14, q15 (13)
8. **Excluded question IDs (and why):** q12, q13 — same reasoning as KPI #1: genuine out-of-scope controls, not escalation candidates. q7 is *included in the denominator* (it's an in-scope question) but *excluded from the numerator* — explained in Assumptions below.
9. **Assumptions:**
   - q7 (the router-misclassification case) is deliberately excluded from the numerator because its answer text is the generic out-of-scope refusal, not an escalation recommendation — the system never told the user "please escalate," it told them "this is outside my scope," which is a different (and arguably worse) failure. Counting it as an "escalation" would blur a routing bug into a QA-gate success story.
   - If a broader definition is used — "any question that didn't get a clean answer, whether via honest escalation or a wrong refusal" — the rate becomes 4 ÷ 13 = **30.8%**. Both numbers are reported so a reviewer can pick the definition that matches their intent; 23.1% is primary because it isolates the metric's actual meaning (the system asking for human help), not routing errors.
10. **Interview explanation:** "3 of 13 in-scope questions triggered an explicit 'please escalate' recommendation — about 23%. There's a 4th case where the system should have engaged and didn't — a router bug, not an escalation — and I keep that separate rather than let it quietly inflate or deflate this number."

### 9. Resolution Time

1. **KPI:** Resolution Time
2. **Final value:** **Cannot be computed — no escalation workflow exists to time.**
3. **Classification:** Not Yet Measured
4. **Exact formula:** N/A
5. **Raw data used:** N/A
6. **Calculation steps:** N/A
7. **Contributing question IDs:** None
8. **Excluded question IDs (and why):** All 15 — Resolution Time (as distinct from Average Response Time) means "how long until a question is fully resolved, including any human step for escalated cases." Confirmed directly in the code (`api/agents/qa.py::FALLBACK_MESSAGE`): the "escalate to L2" recommendation is a static string returned to the user. There is no ticket creation, no queue, no handoff, and therefore no second timestamp (start-of-human-review, end-of-human-review) for any of the 3 escalation cases in this eval to compute a duration from.
9. **Assumptions:** None made. Building this requires, at minimum: (a) an actual escalation integration (ticket/queue system), and (b) timestamps for when a human picks up and closes an escalated question. Neither exists, so no proxy — even a rough one — is defensible; there is no data of any kind to build one from.
10. **Interview explanation:** "This one isn't a measurement gap, it's a missing feature — we don't have an escalation mechanism at all yet, just a text recommendation to the user. Resolution Time becomes measurable the moment we wire up a real escalation path with timestamps, which is on the P1 roadmap, but there's nothing to compute today."

---

## Reconciliation summary

| KPI | Value | Sums to / traces to |
|---|---|---|
| Procurement Self-Service Rate | 69.2% | 9 / 13 (13 = 15 − 2 OOS controls) |
| Unsupported Question Rate | 20.0% | 3 / 15 (all 15 questions) |
| Top Escalation Categories | 4 categories | 4 / 15 (q1, q2, q7, q14) |
| Answer Accuracy | Not computable | 0 / 15 (no ground-truth labels exist) |
| Grounded Response Rate | 78.6% | 11 / 14 (14 = 7 policy + 7 data checks; 3 questions had zero checks) |
| Hallucination Rate | Not computable | bounded complement 3 / 14 = 21.4% (different quantity, not hallucination rate) |
| Average Response Time | p50 3,636ms / p95 6,830ms | 15 / 15 (all questions) |
| SME Escalation Rate | 23.1% (or 30.8% broad) | 3 / 13 (or 4 / 13) |
| Resolution Time | Not computable | 0 / 15 (no escalation timestamps exist) |

Every question ID from q1 to q15 appears in at least one KPI's contributing or excluded list
above — nothing in the 15-question eval was silently dropped from this audit.
