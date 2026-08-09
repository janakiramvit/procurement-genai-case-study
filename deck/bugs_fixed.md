# V2 Bug Log — Agent Loop + Short-Term Memory

Scope note: this log only covers bugs that changed what a real user query got back — a wrong
answer, a wrong refusal, an answer given without evidence. Deployment/tooling issues (bundle
size limits, import paths, an eval script measuring the wrong field) were deliberately excluded
after review — an interviewer evaluating GenAI query-behavior work doesn't need infra hygiene
mixed in with it.

Both entries below were reproduced live against the deployed V2 app
(`novartis-assignment.vercel.app/v2`) on the date of this writeup — not pulled from memory or an
old screenshot. Screenshots of both reproductions exist in this conversation's transcript.

---

## Bug1 — Identical repeat question gets the wrong refusal

**Status: ❌ Still broken** (verified live, not fixed by the commit that claimed to address it)

**Description:** Ask a question, get a correct answer. Ask the *exact same* question again in
the same session, and instead of repeating (or re-verifying) the answer, the system refuses it
as out-of-scope.

**Reproduction:**
1. Turn 1 — `any suppliers related to "vaccine"?` →
   *"The suppliers related to 'vaccine' are: FFF ENTERPRISES INC, GlaxoSmithKline, Aquatactics, LLC, FFF Enterprises, Professional Biological Company, and ASD Healthcare."*
   Trace: `Finished · 2 planner decisions · 1 tool call · 3781ms`
2. Turn 2 (same session) — identical text: `any suppliers related to "vaccine"?` →
   *"That looks outside procurement policy, procurement systems, or spend/PO data..."*
   Trace: `Finished · 1 planner decision · 0 tool calls · 686ms`

**Execution trace for turn 2 (the actual evidence, not a guess):**
```
Conversation Context → 1 prior turn supplied
Iteration 1
FINISH — Planner selected FINISH without calling a procurement capability
Status → finished (planner determined sufficient evidence)
Termination reason: planner determined sufficient evidence
```

**Root cause:** A commit (`d0bcf73`, "recover from blocked/failed V2 agent actions instead of
looping") was believed to fix this — it addresses a *different* mechanism: a blocked duplicate
tool call *within one turn's* multi-step loop, previously retried until the decision budget ran
out. What's actually happening here is different: on a **verbatim repeat** of a prior question,
the planner looks at conversation history and concludes it already has "sufficient evidence,"
then terminates with zero tool calls in a single decision — no retry loop at all. This is
exactly the "memory as evidence" failure mode the eval suite's `a5` case was written to catch
(*"memory is context, not evidence"*), but `a5` only tests a **rephrased** follow-up ("what's our
*current* spend..."), which does trigger a fresh tool call. A byte-for-byte repeat isn't covered
by the same guardrail.

**Fix:** Not yet applied. Next step would be extending the planner's memory-handling rule in
`api/agents/planner.py` to treat an identical repeat the same as a rephrased follow-up — always
requiring fresh evidence rather than trusting history, regardless of phrasing.

---

## Bug2 — Compliance/approval questions answered without retrieving evidence

**Status: ✅ Fixed** (verified live, in a fresh session)

**Description:** Questions asking whether a specific purchase/action is compliant or approved
(e.g. "can we skip a required approval step") could get resolved by the planner's own reasoning
instead of retrieving real policy evidence — meaning the agent could implicitly assert an
approval/compliance answer without ever checking a source or passing through groundedness
verification.

**Reproduction (fresh chat, no history):**
`Can we continue buying laptops from supplier ABC without competitive tender approval?` →
*"I couldn't verify a reliable answer to this from the available procurement knowledge base or data. Please escalate this question to the L2 procurement team."*
Trace: `Finished · 2 planner decisions · 1 tool call · 4083ms`, with an "⚠ Evidence (retrieved, not verified)" panel showing 6 retrieved policy sources (`iucn_procurement_policy.pdf` pages 8/13/14/18, `Procurement_Guidelines_When_to_Engage_Procurement.pptx` slide 14, `Procurement_Guidelines.pptx` slide 9).

**What this confirms:** `policy_answer` was actually called (1 tool call, 6 sources retrieved) —
before the fix, this same question was observed routing straight to FINISH with **0 tool calls**.
The answer here still hits the safe-fallback/escalation path because groundedness failed on this
specific attempt — that's the QA gate working correctly, a separate and expected behavior, not
part of the bug.

**Fix:** Two planner prompt rules were added: (1) `policy_answer` must be called before FINISHing
whenever a question asks about an approval, tender/RFP, contract, threshold, sourcing, or
compliance requirement for a specific purchase/supplier/spend decision — the planner may never
resolve this from its own reasoning; (2) a companion guardrail so the planner doesn't
over-trigger just because a question mentions "procurement" in passing (e.g. "can we build a
procurement dashboard" is a product question, not a policy one). A regression eval case (`a6`)
was added to `eval/eval_questions_agent.json` to catch this going forward.

---

## UI Improvement — Agent trace readability

**Not a bug fix — a presentation-layer change to how the above traces are shown to the user.**

**Before:** `AgentTrace.tsx` rendered the raw backend event stream directly — bare event names
like `planner_decision`, `tool_call`, `qa_result` with no interpretation layer.

**After:** The same underlying data (no new backend field) is relabeled onto a
**Plan → Act → Verify → Observe → Finish** vocabulary — e.g. `"FINISH — Planner selected FINISH
without calling a procurement capability"` and `"VERIFY — Policy Groundedness QA: PASS (score
5/5)"`. The policy QA score, when shown, is read from the existing `groundedness` response field,
correlated to the right VERIFY line by chronological order (both are appended per-iteration in
the same sequence server-side).

**Why it matters for this changelog specifically:** the Bug1 reproduction above was diagnosable
*because* of this change — `"FINISH — Planner selected FINISH without calling a procurement
capability"` is a direct, readable statement of what went wrong, not something that had to be
inferred from a raw event dump.
