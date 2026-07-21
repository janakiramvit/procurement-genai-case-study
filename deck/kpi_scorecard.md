# Procurement Copilot — P0 KPI Scorecard

Source of truth for every number below: `eval/eval_results.json` (the 15-question offline
eval, same one already reported in DESIGN.md and the deck) and direct inspection of
`api/agents/*.py`. Nothing here comes from production usage — **there is no production usage**.
No auth, no telemetry, no user identity, no feedback capture, and no real query traffic exist
yet. That constraint shapes almost every row below, and it's stated plainly rather than papered
over with an estimate that looks more solid than it is.

## How every row was classified

- **Measured** — a direct, already-computed number from the 15-question eval. No modeling.
- **Proxy (P0)** — the eval data doesn't measure the KPI directly, but supports a defensible,
  fully-shown calculation that approximates it. Every proxy below states its formula, its inputs,
  and its sample size so a reviewer can recompute or challenge it.
- **Not Yet Measured** — no defensible P0 number exists, proxy or otherwise, because the
  underlying capability (telemetry, user identity, escalation integration, real usage) doesn't
  exist in the system yet. The table says what P1 needs to build to measure it, not a placeholder
  number.

Nothing below was invented. Where a number required a calculation, the calculation is shown in
the Methodology Appendix at the end of this document.

---

## Final KPI Table

### North Star

| KPI | P0 Value | Status | Basis |
|---|---|---|---|
| Procurement Self-Service Rate | **69.2%** (9 of 13 in-scope eval questions) | Proxy | % of in-scope eval questions that received a complete, non-escalated, correctly-routed answer. See Appendix A. |

### Adoption

| KPI | P0 Value | Status | What P1 needs |
|---|---|---|---|
| Active Users | Not Yet Measured | — | No auth/user identity exists. Requires session or account tracking. |
| Queries per User | Not Yet Measured | — | Same as above — no per-user attribution possible today. |
| Repeat Usage Rate | Not Yet Measured | — | Requires user identity + longitudinal usage logging. |
| User Retention | Not Yet Measured | — | Requires user identity + usage logging over time (weeks, not one session). |

*All four are architecturally blocked on the same missing capability: there is no concept of "a
user" in the current system. This is one P1 investment (auth + basic analytics), not four.*

### Coverage

| KPI | P0 Value | Status | Basis |
|---|---|---|---|
| Use Case Self-Service Rate — Supplier Onboarding | Not Yet Measured | — | Only 2 eval questions touch this area (n too small for a rate; see Appendix B) |
| Use Case Self-Service Rate — Purchase Orders | Not Yet Measured | — | Eval questions weren't designed against this specific taxonomy; see Appendix B |
| Use Case Self-Service Rate — Invoice Processing | Not Yet Measured | — | Only 2 eval questions touch this area |
| Use Case Self-Service Rate — Contracts | Not Yet Measured | — | Only 1-2 eval questions touch this area |
| Use Case Self-Service Rate — Payments | Not Yet Measured | — | Zero eval questions specifically target payments |
| Business Unit Self-Service Rate | Not Yet Measured | — | No business-unit metadata is captured anywhere in the system |
| Vendor Self-Service Rate | Not Yet Measured | — | No vendor/requester identity is captured |
| Unsupported Question Rate | **13.3%** (2 of 15 eval questions) | Proxy | Router correctly classified 2/2 deliberately-included out-of-scope questions as OUT_OF_SCOPE. This reflects the eval set's design (2 of 15 were intentionally off-topic), not a real query distribution. See Appendix C. |
| Top Escalation Categories | Qualitative (4 categories identified) | Proxy | Every eval question that triggered an escalation recommendation or a routing failure, categorized. See Appendix D. |

### Trust

| KPI | P0 Value | Status | Basis |
|---|---|---|---|
| Answer Accuracy | Not Yet Measured | — | No independent human/expert fact-check against ground truth has been performed. Groundedness (below) checks "is this supported by a cited source," not "is this the objectively correct real-world answer" — a related but distinct claim. P1 needs a small human-graded gold-answer set. |
| Grounded Response Rate | **78.6%** (11 of 14 groundedness checks passed) | Measured | (4 policy passes + 7 data passes) / (7 policy attempts + 7 data attempts) = 11/14. Directly computed from existing eval aggregates — no modeling. |
| User Feedback (👍/👎) | Not Yet Measured | — | Not built. No feedback UI exists in the current app. Listed as a P1 roadmap item already in DESIGN.md. |
| Hallucination Rate | Not Yet Measured (bounded, not audited) | — | The QA gate suppresses ungrounded answers rather than showing them (21.4% of attempted answers were caught and replaced with a safe fallback — the complement of Grounded Response Rate). This bounds hallucinations *reaching the user* architecturally, but no adversarial/red-team test has tried to induce one, so "near-zero" is a design property, not a measured rate. |

### Efficiency

| KPI | P0 Value | Status | Basis |
|---|---|---|---|
| Average Response Time | **p50 3.6s / p95 6.8s** | Measured | Direct from eval aggregates (`p50_latency_ms`, `p95_latency_ms`), full pipeline including QA verification calls. |
| SME Escalation Rate | **23.1%** (3 of 13 in-scope questions) explicit, **30.8%** (4 of 13) including one router-misclassification failure | Proxy | See Appendix A — two numbers given because a router failure that produces a wrong refusal is a different failure mode than an honest "please escalate" and the two shouldn't be silently merged. |
| Resolution Time | Not Yet Measured | — | No escalation-to-human workflow exists (recommending escalation is a text message today, not an integration — see DESIGN.md §8). Nothing to time. |

### Business Value

| KPI | P0 Value | Status | Basis |
|---|---|---|---|
| SME Hours Saved | Not Yet Measured | — | Requires a real baseline (actual ticket volume, actual SME handling time per ticket) that doesn't exist. Deliberately not estimated — see the earlier business-impact discussion in this project where the same call was made for ROI. |
| Cost per Resolution | Not Yet Measured (formal) — modeled compute-only estimate available | — | No token-usage telemetry is implemented, so real cost isn't observed. A bounded compute-cost-only model is in Appendix E (~$0.001/query, order-of-magnitude) but explicitly excludes hosting, engineering amortization, and SME-time value — it is not "cost per resolution." |
| Procurement Productivity | Not Yet Measured | — | Business-process-level metric requiring real usage data across many users and a defined productivity baseline. Out of reach until well into P1/pilot. |

---

## Appendix A — Procurement Self-Service Rate & SME Escalation Rate (methodology)

Of the 15 eval questions, 2 (q12, q13) are deliberately out-of-scope control questions — they
test refusal correctness, not self-service capability, so they're excluded from this
denominator. That leaves **13 in-scope questions**.

Per-question outcome (from `eval/eval_results.json`):

| Outcome | Questions | Count |
|---|---|---|
| Correctly routed, answer passed QA, no escalation language | q3, q4, q5, q6, q8, q9, q10, q11, q15 | 9 |
| Correctly routed, but answer included explicit escalation/"couldn't verify" language | q1, q2, q14 | 3 |
| Router misclassified as OUT_OF_SCOPE (should have been POLICY) — user got a refusal, not an answer or an escalation note | q7 | 1 |

- **Procurement Self-Service Rate (proxy) = 9 / 13 = 69.2%** — the share of in-scope questions
  that resolved cleanly with no caveat.
- **SME Escalation Rate, explicit-only = 3 / 13 = 23.1%** — questions where the system itself
  recommended escalation.
- **SME Escalation Rate, including routing failures = 4 / 13 = 30.8%** — if a wrongly-refused
  question is treated as an escalation-worthy miss too (arguably worse than an honest escalation,
  since the user wasn't even told to check with L2).

**Caveats that matter more than the numbers:** n=13. This is a hand-written synthetic set
designed to include hard cases (an unresolved source-doc placeholder, thin retrieval coverage,
an undocumented term) specifically to stress-test the QA gate — it is not a sample of real
question frequency or difficulty. A real self-service rate requires real query logs.

## Appendix B — Why the 5 use-case sub-rates are Not Yet Measured

Mapping the 15 eval questions onto Supplier Onboarding / Purchase Orders / Invoice Processing /
Contracts / Payments:

| Use case | Matching eval questions | n |
|---|---|---|
| Supplier Onboarding | q2 (sourcing event), q8 (Ariba registration) | 2 |
| Purchase Orders | q1, q3, q5, q14 (all touch PO data or PO/contract thresholds) | 4 |
| Invoice Processing | q9, q10 | 2 |
| Contracts | q1, q11, q15 | 3 (overlaps with PO) |
| Payments | none | 0 |

n=0-4 per bucket isn't a rate — it's an anecdote with a percentage sign on it. Reporting "100%
Supplier Onboarding self-service" from n=2 (one of which, q2, actually failed groundedness) would
overstate confidence a VP-level reviewer should not be given. Recommend: keep these as
qualitative coverage notes until a real eval set sized per-category (10-20 questions per use
case, minimum) exists.

## Appendix C — Unsupported Question Rate caveat

2 of the 15 eval questions were deliberately written to be out-of-scope, specifically to test
refusal behavior. 13.3% is therefore a property of the eval set's design, not an observation
about how often real users will ask off-topic questions. Real-world unsupported-question rate is
unknown until there's real query traffic to measure it against.

## Appendix D — Top Escalation Categories (qualitative, n too small to rank)

The 4 problem cases in the eval set, categorized by root cause:

1. **Source document itself is incomplete.** q1 ($70k laptop threshold) retrieves a policy slide
   with an unresolved "$[C]" placeholder — the source material, not the model, is missing the
   answer.
2. **Retrieval recall gap on a covered topic.** q2 (add supplier to sourcing event) — the corpus
   has relevant content, but naive chunking didn't surface it in the top-6 results.
3. **Mixed-category answer where the policy leg wasn't confidently grounded.** q14 (DVBE
   supplier spend) — the data half succeeded; the policy-qualification half didn't clear the
   groundedness bar.
4. **Term absent from the corpus entirely, causing a router miss.** q7 (Leveraged Procurement
   Agreement) — not documented anywhere in the KnowledgeBase, and the router defaulted to
   refusing outright rather than routing to a policy search that would have honestly come up
   empty.

These are four distinct failure modes, not four instances of the same problem — worth keeping
distinct in any P1 remediation plan rather than treating "groundedness failure" as one bucket.

## Appendix E — Modeled compute-cost-per-query estimate (not a measured KPI)

No token-usage telemetry exists in the deployed system, so this is a model, built from two
things that *are* verifiable: the exact number of LLM calls per category (read directly from
`api/agents/orchestrator.py`, `rag_agent.py`, `data_agent.py`) and approximate public gpt-4o-mini
/ text-embedding-3-small pricing. Assumed token sizes per call are estimates based on known
prompt construction (e.g., the RAG agent's context is 6 retrieved chunks at ~600 tokens each);
they are not measured. Treat this as order-of-magnitude only.

| Category | LLM calls | Est. input tokens | Est. output tokens | Est. cost/query |
|---|---|---|---|---|
| OUT_OF_SCOPE | 1 (router) | ~280 | ~30 | ~$0.00006 |
| DATA | 3 (router, SQL gen, SQL summarize) | ~2,780 | ~240 | ~$0.0006 |
| POLICY | 3 chat + 1 embedding (router, RAG answer, groundedness judge) | ~7,930 | ~280 | ~$0.0014 |
| BOTH (both legs pass, synthesizer runs) | 6 chat + 1 embedding | ~10,930 | ~690 | ~$0.0021 |

Weighted by the actual category mix observed in the 15-question eval (2 BOTH, 5 POLICY, 5 DATA,
3 OUT_OF_SCOPE): **~$0.001 per query, compute only.** This excludes hosting/serverless
invocation cost, engineering time, and any SME-time-value offset — it is a lower bound on one
input to a real "Cost per Resolution" figure, not the figure itself.
