# Procurement Copilot — Presentation Content (source of truth for slide-building)

Every claim below is grounded in the actual implementation: `api/agents/*.py`, `scripts/*.py`,
`DESIGN.md`, and `eval/eval_results.json`. Two corrections vs. the original brief, confirmed
with you:

1. **SQL verification exists** (`api/agents/qa.py::check_sql_groundedness`) — it's a
   deterministic check that the generated SQL executed without error and returned rows. It does
   **not** verify the numbers are semantically/factually correct beyond that. Both slides below
   state this precisely rather than "not implemented."
2. **An eval harness exists and has been run** (`scripts/evaluate.py`, `eval/eval_questions.json`,
   `eval/eval_results.json`) — 15 questions, real results. Slide 11 presents it as implemented,
   then describes what a production/CI-integrated version would add.

No LangChain, LangGraph, CrewAI, Pinecone, Redis, Kubernetes, or Azure AI Search anywhere in the
stack — confirmed against `requirements.txt` and every import in `api/agents/`.

---

## Slide 1 — Title

**Title:** Procurement Copilot — L1 AI Helpdesk
**Subtitle:** Sr. Procurement AI & Analytics Lead — Case Study (REQ-10069230)

**Project objective:** Build a working prototype of a Level 1 procurement helpdesk that answers
questions from procurement policy documents and structured spend/PO data through a single chat
interface, with a working example implemented end-to-end (not just designed).

**One-sentence value proposition:** A multi-agent system that answers procurement policy and
spend-data questions from real source documents and real data, and explicitly refuses to answer
rather than guess when it can't verify the answer.

### Speaker notes
- This is a prototype built in a single time-boxed session, not a production system — say that
  up front so scope expectations are calibrated correctly for the rest of the talk.
- Emphasize "explicitly refuses rather than guesses" — this is the throughline for the whole
  deck and the thing most worth defending in Q&A.

### Likely interviewer questions
- "Is this live, or a mockup?" 
- "How long did this take to build?"

### Suggested answers
- "It's live — [novartis-assignment.vercel.app], I can drive it right now." (only say this if
  it's actually still deployed and working at interview time — verify beforehand.)
- State the actual time honestly (a single focused session), and frame it as evidence of
  hands-on GenAI capability under real time pressure, per the case study's stated objective.

---

## Slide 2 — Procurement Knowledge Problem

**Frame as a business problem, not a technology problem.**

- **Fragmented policy documents:** Procurement policy knowledge is spread across 16 separate
  documents in 3 different formats (PDF, DOCX, PPTX) — contract/PO threshold rules, Ariba
  supplier and sourcing-event workflows, contract authoring/compliance guides, and UNSPSC
  classification references. No single document answers a typical question end-to-end.
- **Structured spend/PO data locked away:** Historical purchase order and invoice data
  (152,451 PO line items after cleaning, 2,466 invoices) exists as raw exports. Answering "what
  did we spend with Supplier X" requires someone who can write SQL or use a BI tool — not
  something a requester or an L1 agent can self-serve.
- **Repetitive L1 questions:** The same categories of question recur — "do I need a contract or
  a PO," "how do I add a supplier to a sourcing event," "what's the UNSPSC code for X." These are
  pattern-matchable against existing documentation and data, not judgment calls that need a
  human expert every time.
- **SME dependency:** Every one of those repetitive questions currently requires a procurement
  SME's time to either look it up or explain the process, which doesn't scale and creates a
  response-time bottleneck for requesters.

### Speaker notes
- Ground this in the case study's own sample questions (verbatim from the brief): "$70k laptops
  — contract, PO, or engage procurement?" and "add a supplier to a sourcing event."
- Don't editorialize with invented statistics about ticket volume or SME hours — the brief and
  the provided data don't include that; keep this qualitative and defensible.

### Likely interviewer questions
- "How do you know these are the actual pain points, not assumptions?"
- "What volume of L1 questions does procurement actually get?"

### Suggested answers
- "These come directly from the case study brief and the provided sample questions — I didn't
  have ticket volume data, so I'm not going to fabricate a number. In a real engagement, the
  first thing I'd pull is actual L1 ticket categorization data to validate and prioritize."

---

## Slide 3 — Business Impact

**Current pain points:**
- Requesters wait on a human response for questions that are, in principle, answerable from
  existing documentation and data.
- Procurement SME time is spent on repetitive lookups instead of higher-judgment work.
- Answers may be inconsistent across different SMEs/agents answering the same question.
- Spend/PO data insight is gated behind whoever can write SQL or has BI tool access.

**Why an AI helpdesk helps:**
- Deflects the class of questions that's answerable from existing static content, freeing SME
  time for genuinely ambiguous cases.
- Gives requesters a consistent, source-cited answer instead of one that depends on which SME
  they happened to reach.
- Opens self-service spend/PO analytics to non-technical requesters.
- Makes uncertainty visible instead of hidden: when the system can't verify an answer, it says so
  and recommends escalation, rather than silently giving an inconsistent or wrong one.

**Explicitly not claimed:** No ROI, cost-savings, deflection-rate, or time-saved figures are
stated anywhere in this deck. None were measured — the prototype has not been used in a live
setting, and no baseline ticket data was available. Any such number in a real proposal would need
to come from measuring actual usage after a pilot.

### Speaker notes
- Say the "explicitly not claimed" paragraph out loud, don't just leave it as a slide note — it
  preempts the most obvious credibility challenge in the room.

### Likely interviewer questions
- "What's the expected ROI?" / "How much time would this save?"
- "Have you validated this reduces SME workload?"

### Suggested answers
- "I deliberately didn't estimate ROI — I don't have real ticket volume, deflection rate, or
  SME-hours-per-ticket data, and I'd rather say that honestly than make up a number. That's
  exactly the kind of baseline I'd want to establish in a pilot before promising savings."

---

## Slide 4 — Prototype Scope (Implemented)

**Supported question types (implemented, verified working):**
1. Policy/process questions answerable from the 16-document KnowledgeBase corpus (contract vs.
   PO thresholds, Ariba/Icertis how-tos, supplier lifecycle, UNSPSC taxonomy concepts) — routed
   to the RAG path.
2. Structured-data questions over the purchase order, invoice, and UNSPSC reference tables
   (spend by supplier/department, PO counts, UNSPSC code lookups, invoice dispute/settlement
   stats) — routed to the SQL path.
3. Mixed questions needing both a policy rule and a data lookup (e.g., "is $70k above our
   contract threshold" needs both a threshold rule and, ideally, a UNSPSC classification) —
   routed to both paths, merged by a synthesizer.
4. Off-topic/out-of-scope questions — correctly refused by the router, at the router step only
   (no RAG/SQL agents invoked).

**Unsupported question types (explicitly not implemented):**
1. Multi-turn follow-ups referencing prior conversation context ("what about last year?") — no
   conversation memory; each question is handled statelessly.
2. Questions needing live/real-time Ariba, SAP, or Icertis data — the system only has the static
   document/CSV/XLSX exports provided with the case study, no live API integration.
3. Any write/transactional action (create a PO, add a supplier, submit a sourcing event) — the
   system is read-only and informational; it can explain a documented procedure, but cannot
   execute it.
4. Anything requiring data outside the provided corpus (current live spend, real Novartis-
   specific policy beyond what's in the KnowledgeBase, anything post-dataset).
5. Anything requiring user identity or role (e.g., "what's my approved spend limit") — no
   authentication, no user context, single shared L1 desk for all users.

| Category | Example | Status |
|---|---|---|
| Policy Q&A (RAG) | "Do I need a contract for a $70k purchase?" | Implemented |
| Structured data (SQL) | "What's our total spend with IBM?" | Implemented |
| Mixed policy + data | "$70k laptops — contract, PO, or engage procurement?" | Implemented |
| Out-of-scope refusal | "What's the weather today?" | Implemented |
| Multi-turn follow-up | "And what about last quarter?" | Not implemented |
| Live ERP data | "What's in the sourcing event right now in Ariba?" | Not implemented |
| Transactional actions | "Add this supplier to the sourcing event" | Not implemented |
| User/role-scoped answers | "What's my approval limit?" | Not implemented (no auth) |

### Speaker notes
- Lead with the table — it's the single most interview-defensible artifact in this deck because
  it draws the scope line explicitly instead of letting the interviewer assume more was built.

### Likely interviewer questions
- "Why didn't you implement conversation memory / live integration in this timeframe?"
- "Could a user accidentally think this can take actions it can't?"

### Suggested answers
- "Given the time available, I scoped to the read-only, single-turn core that directly answers
  the brief's sample questions, and treated memory/live integration/actions as iteration 2 —
  they're architecturally additive, not blocked by anything in the current design."
- "The system never claims to perform an action — it only explains documented procedures. That
  said, in a production version I'd want an explicit UI affordance making that read-only nature
  obvious to the user, not just implicit in the prompt."

---

## Slide 5 — Why This Architecture?

For each decision: **Decision → Reason → Alternative considered → Trade-off**

**1. LLM Router (single classification call before any retrieval)**
- *Reason:* One question can need policy knowledge, data lookup, both, or neither — decide that
  first, cheaply, before doing more expensive work.
- *Alternative considered:* Always run both RAG and SQL agents on every question, merge
  unconditionally.
- *Trade-off:* Router adds one extra LLM call and is itself a point of failure (measured 86.7%
  accuracy on the eval set — see Slide 11) — but running both agents on every question would
  roughly double cost/latency and add irrelevant citations/SQL to answers that don't need them.

**2. RAG for policy questions**
- *Reason:* Policy answers must be grounded in the actual KnowledgeBase text, not the model's
  general training knowledge — procurement policy specifics (thresholds, workflows) aren't
  something a general-purpose LLM can be trusted to know correctly.
- *Alternative considered:* Fine-tuning a model on the policy corpus.
- *Trade-off:* RAG is transparent (citable, updatable by just re-ingesting docs) but retrieval
  quality is a real constraint — measured 83.3% retrieval hit-rate on the eval set, i.e. not
  perfect. Fine-tuning would be far more expensive and less transparent/auditable for a
  compliance-sensitive domain, and wasn't appropriate at this scope/timeline regardless.

**3. Text-to-SQL for structured data**
- *Reason:* PO/invoice data is naturally tabular and aggregation-heavy — SQL is the right tool,
  and a schema-constrained SQL generator is far more auditable than free-form code generation.
- *Alternative considered:* A pandas/code-execution agent (model writes and runs Python over the
  data directly).
- *Trade-off:* SQL generation is constrained to what's expressible in one query per turn (no
  multi-step analysis), but it's safely sandboxable (validated, read-only, single-statement) in a
  way that arbitrary code execution is not.

**4. Verification/QA layer (two different strategies, not one)**
- *Reason:* RAG answers are free text needing a judgment call about groundedness; SQL answers
  already carry their own ground truth in the query result.
- *Alternative considered:* One uniform "ask a second LLM to check the answer" step for both
  paths.
- *Trade-off:* Two separate, simpler mechanisms (an LLM-judge for RAG, a deterministic check for
  SQL) instead of one general one — more code paths to maintain, but each one is easier to reason
  about and the deterministic SQL check is strictly cheaper and more reliable than an LLM
  re-verifying a fact it could just read off the result set.

**5. Simple deployment (single Vercel project, no dedicated infra)**
- *Reason:* Appropriate for a scoped prototype with a static, small corpus and no need for
  horizontal scaling, user isolation, or persistent state.
- *Alternative considered:* Separate hosted vector DB + dedicated backend service (e.g.
  containerized API on its own compute).
- *Trade-off:* Zero infrastructure to manage or pay for at this scale, one-command deploy — but
  the current design won't scale past Vercel serverless function limits (bundle size, execution
  duration) without re-architecting, and there's no persistent database, caching layer, or
  horizontal scaling story built in.

### Speaker notes
- The pattern across every row is the same: chose the simpler, more auditable option and
  explicitly named its ceiling, rather than the more capable/complex option. That consistency is
  worth calling out as a deliberate philosophy, not five unrelated choices.

### Likely interviewer questions
- "Why not just use LangChain/LangGraph to build the agent orchestration — wouldn't that be
  faster?"
- "Isn't a router just adding a point of failure?"

### Suggested answers
- "For a fixed, small number of well-defined paths (4 categories, 2 specialist agents), an
  explicit function-call graph is easier to reason about, debug, and unit-test than a framework's
  agent abstraction — and it doesn't add a dependency I'd have to explain the internals of two
  years from now. I'd reach for a framework if the tool/agent surface grew large enough that
  hand-rolled orchestration became the bottleneck, not before."
- "Yes, and I measured that — 86.7% router accuracy on the eval set, not 100%. The alternative
  (always running both agents) trades that failure mode for guaranteed extra cost and latency on
  every request, including the majority that only need one path."

---

## Slide 6 — Solution Architecture

*(Content for you to redraw as a diagram — not a description of an image already made.)*

```
                              User Question
                                   |
                                   v
                    ┌─────────────────────────────┐
                    │           Router              │  (1 LLM call, gpt-4o-mini)
                    │  classifies into one of:      │
                    │  POLICY / DATA / BOTH /       │
                    │  OUT_OF_SCOPE                 │
                    └─────────────────────────────┘
                                   |
        ┌──────────────────────────┼──────────────────────────┐
        |                          |                          |
   (POLICY/BOTH)               (DATA/BOTH)              (OUT_OF_SCOPE)
        v                          v                          v
┌───────────────┐         ┌───────────────┐          ┌────────────────┐
│  Policy path   │         │   SQL path     │          │  Canned refusal │
│                │         │                │          │  message,       │
│ 1. Embed query │         │ 1. LLM writes  │          │  no further      │
│ 2. Cosine-sim  │         │    SQL against │          │  agents called   │
│    top-6 chunks│         │    fixed schema│          └────────────────┘
│ 3. LLM answers │         │ 2. Safety guard│
│    only from   │         │    validates   │
│    retrieved   │         │    (SELECT-only│
│    chunks, with│         │    no DDL/DML) │
│    citations   │         │ 3. Execute on  │
└───────────────┘         │    read-only   │
        |                  │    DuckDB      │
        |                  │ 4. LLM         │
        |                  │    summarizes  │
        |                  │    result rows │
        |                  └───────────────┘
        v                          v
┌───────────────┐         ┌───────────────┐
│ Verification:  │         │ Verification:  │
│ LLM-judge      │         │ deterministic  │
│ groundedness   │         │ check — did    │
│ check against  │         │ SQL execute    │
│ retrieved      │         │ without error, │
│ chunks         │         │ return rows?   │
└───────────────┘         └───────────────┘
        |                          |
        └────────────┬─────────────┘
                      v
        ┌─────────────────────────────┐
        │  Both passed & category=BOTH │──> Synthesizer (1 LLM call, merges
        │  → Synthesizer                │    both answers, preserves citations)
        │  Only one passed → that       │
        │  answer + caveat note         │
        │  Neither passed → safe        │
        │  fallback message             │
        └─────────────────────────────┘
                      |
                      v
                  Response
     (answer text, citations, SQL used, per-step
      latency, groundedness verdicts — returned as
      one complete JSON payload, not streamed)
```

Key structural facts for the diagram:
- This is a **deterministic graph**, not an autonomous agent loop — every arrow above is a fixed
  code path, not a model deciding what to call next.
- The Policy path and SQL path run **independently** when category is BOTH — there's no
  dependency between them; the Synthesizer is the only step that combines their outputs.
- The **Verification step is different per path** (LLM-judge vs. deterministic) — don't draw it
  as one uniform box; it's two distinct mechanisms with a shared "pass/fail gate" role.
- **No streaming** — the diagram should show one round-trip from Router to Response, not a
  progressive/streaming arrow.

### Speaker notes
- If drawing this live, draw the router diamond first, then branch — the branching-then-
  reconverging shape is the one thing that must read clearly at a glance.

### Likely interviewer questions
- "What happens if the router misclassifies BOTH questions as just DATA?"
- "Is there any loop or retry in this graph?"

### Suggested answers
- "Then only the SQL path runs, and the user gets a data answer without the policy context — the
  15-question eval measured this: policy path was skipped when it should have run in some BOTH-
  labeled cases (see the DVBE example in the eval results). No retry — it's a single classification
  with a fail-safe default to OUT_OF_SCOPE if the model returns an unrecognized category."
- "No loops. Each box runs at most once per request. That's a deliberate simplicity choice, not
  an oversight — see Slide 5's router rationale."

---

## Slide 7 — Detailed Design

### Router
- **Purpose:** Classify the question so only relevant agent(s) run.
- **Inputs:** Raw user question string.
- **Outputs:** `{category: POLICY|DATA|BOTH|OUT_OF_SCOPE, reasoning: string}`
- **Model used:** `gpt-4o-mini`, temperature 0, JSON-object response format.
- **Failure behavior:** If the model returns a category string outside the four allowed values,
  the code defaults to `OUT_OF_SCOPE` (fail-safe, not fail-open).

### Retriever (part of the RAG/policy path)
- **Purpose:** Find the most relevant KnowledgeBase passages for a policy question.
- **Inputs:** Query string.
- **Outputs:** Top-6 chunks (source filename, page/slide/document location, text, similarity
  score), then a generated answer citing them by number.
- **Model used:** `text-embedding-3-small` for the query embedding; brute-force cosine
  similarity (numpy dot product against a precomputed, L2-normalized 1,953 × 1,536 matrix) for
  ranking — no vector database. Answer generation uses `gpt-4o-mini`, temperature 0, instructed
  to answer only from the provided passages and to say so if they're insufficient.
- **Failure behavior:** If retrieval doesn't surface the right passage, or the model doesn't
  faithfully follow the "answer only from context" instruction, that's not caught here — it's
  caught downstream by the Verification layer, not by the retriever itself.

### SQL Generator
- **Purpose:** Turn a data question into a single SQL query against the known schema.
- **Inputs:** Query string + a static schema description (`api/_store/schema_description.md`)
  covering the `purchase_orders`, `invoices`, and `unspsc_hierarchy` tables.
- **Outputs:** Raw SQL string (as JSON: `{"sql": "..."}`).
- **Model used:** `gpt-4o-mini`, temperature 0, JSON-object response format.
- **Failure behavior:** No self-correction/retry loop — if the SQL is invalid or unsafe, it is
  not regenerated automatically; it's caught and rejected by the SQL Safety Guard.

### SQL Safety Guard
- **Purpose:** Prevent the generated SQL from doing anything other than a safe, read-only lookup.
- **Inputs:** Raw SQL string from the SQL Generator.
- **Outputs:** A validated, auto-limited SQL string, or a rejection (`ValueError`).
- **Model used:** None — pure Python logic (regex/keyword checks), not an LLM step.
- **Logic:** Must start with `SELECT` or `WITH`; rejects any query containing a second `;`
  (blocks statement chaining); rejects a fixed keyword blocklist (`INSERT`, `UPDATE`, `DELETE`,
  `DROP`, `ALTER`, `ATTACH`, `DETACH`, `PRAGMA`, `CREATE`, `COPY`, `EXPORT`, `IMPORT`, `CALL`,
  `INSTALL`, `LOAD`, `VACUUM`, `TRUNCATE`, `GRANT`, `REVOKE`, `SET`); auto-wraps with
  `LIMIT 200` if no `LIMIT` is present. Execution then happens against a DuckDB connection opened
  with `read_only=True`.
- **Failure behavior:** A rejected query is surfaced as an error string, which the Verification
  layer treats as a failed check (no fallback SQL is attempted).
- **Explicit limitation:** This is a regex/keyword allowlist, **not a full SQL parser/AST
  analysis** (e.g., not using `sqlglot`). Sufficient because the SQL is model-generated against a
  fixed schema, not raw untrusted input — but not a substitute for AST-level validation if this
  were ever exposed to less-trusted input.

### Verification Layer (two mechanisms)
- **Policy path — LLM-judge groundedness check**
  - *Purpose:* Verify every claim in the RAG answer is actually supported by the cited passages.
  - *Inputs:* The generated answer text + the retrieved chunks it cited.
  - *Outputs:* `{passed: bool, score: 1-5, reasoning: string, method: "llm_judge"}`; passes only
    at score ≥ 4.
  - *Model used:* `gpt-4o-mini`, temperature 0, JSON-object response format.
  - *Failure behavior:* If it fails, the RAG answer is discarded — replaced by a fallback
    message (pure POLICY) or a caveat note appended to the SQL answer (BOTH, if SQL passed).
- **Data path — deterministic execution check**
  - *Purpose:* Confirm the SQL actually ran and returned data.
  - *Inputs:* The SQL execution result (success/error, row count).
  - *Outputs:* `{passed: bool, reasoning: string, method: "deterministic"}`.
  - *Model used:* None — plain Python check of whether execution raised an error.
  - *Explicit limitation, stated precisely:* **This verifies execution succeeded, not that the
    answer is numerically/semantically correct.** It does not independently confirm the SQL
    logic matches the user's intent (e.g., it cannot detect a query that runs successfully but
    filters on the wrong column). Semantic/numeric correctness verification is **not
    implemented**.
  - *Failure behavior:* If SQL execution errored (including being blocked by the Safety Guard),
    the SQL answer is discarded — same fallback/caveat pattern as above.

### Synthesizer
- **Purpose:** Merge a policy answer and a data answer into one coherent response, only when both
  are needed and both passed verification.
- **Inputs:** Original question + the RAG answer text + the SQL answer text.
- **Outputs:** One merged natural-language answer, instructed to preserve citation markers.
- **Model used:** `gpt-4o-mini`, temperature 0, plain text (not JSON).
- **Failure behavior:** Only invoked when category is `BOTH` and both verification checks
  passed. If only one path passed, its answer is returned directly with an appended caveat about
  the other path; if neither passed, the canned fallback message is returned and the Synthesizer
  is never called.

### Speaker notes
- If asked to whiteboard any one component, the SQL Safety Guard is the easiest to defend in
  concrete terms — walk through the actual blocklist and the LIMIT auto-wrap live.

### Likely interviewer questions
- "Why gpt-4o-mini for everything instead of a stronger model for generation and a cheaper one
  for classification?"
- "What stops the SQL Generator from writing an infinite/expensive query?"

### Suggested answers
- "Cost/latency consistency during a time-boxed build — one model to reason about everywhere.
  In production I'd A/B a stronger model specifically for final answer generation, since that's
  the output quality that matters most, and keep the cheap model for routing/judging."
- "The auto-`LIMIT 200` wrap caps result size; there's no query-timeout enforcement in the
  current build, which is a real gap for a table this size if someone crafted a deliberately
  expensive aggregate — worth flagging as a limitation, not something I'd claim is handled."

---

## Slide 8 — Trust, Safety & Verification

**Policy verification (implemented):** An LLM-judge (`gpt-4o-mini`) checks whether every claim in
a generated policy answer is actually supported by the passages it cites, scoring 1-5 and
passing only at ≥4. This is a probabilistic check, not a guarantee — the judge is itself an LLM
call and can be wrong.

**SQL verification (implemented, narrower than "answer verification"):** A deterministic check
confirms the generated SQL executed without error and returned rows. **This does not verify the
returned numbers are correct** — it cannot detect a query that runs successfully but answers a
subtly different question than the one asked. Semantic/numeric correctness verification (e.g.
an independent recomputation, or a second model cross-checking the SQL logic against the
question) is **not implemented**.

**Safe refusal (implemented):** If either verification check fails, the system does not present
the unverified answer. It returns: *"I couldn't verify a reliable answer to this from the
available procurement knowledge base or data. Please escalate this question to the L2
procurement team."*

**Escalation (partially implemented — message only, no mechanism):** The fallback message
*recommends* escalating to L2. There is **no actual escalation integration** — no ticket
creation, no email, no handoff to a human queue. It is text guidance shown to the user, nothing
more.

**Known limitations of this trust layer, stated explicitly:**
- The LLM-judge for policy groundedness is itself a model call and can misjudge — on the 15-
  question eval set it correctly rejected a genuinely ungrounded answer (see the $[C] placeholder
  finding) but also rejected at least one answer that was arguably a reasonable honest refusal
  (measured policy groundedness pass rate: 57.1%, 4 of 7 policy-path questions).
- SQL verification does not catch logically-wrong-but-executable SQL.
- There is no verification at all for the Router's classification itself, beyond the fail-safe
  default to `OUT_OF_SCOPE` on an invalid category value.
- No human-in-the-loop review of any answer before it reaches the user — verification is fully
  automated.

### Speaker notes
- This slide is the one place in the deck where being maximally precise about what "SQL
  verification" does and doesn't mean matters most — don't let the word "verification" imply
  more than the deterministic execution check actually provides.

### Likely interviewer questions
- "So if the SQL agent writes a query that runs but answers the wrong question, does the system
  catch that?"
- "What does 'escalate to L2' actually do right now?"

### Suggested answers
- "No — that's the real gap. It'll pass verification because it executed and returned rows, even
  if the WHERE clause doesn't match the intent. Catching that needs either a second model
  cross-checking the SQL against the question, or a small set of hand-verified reference
  queries to sanity-check against — both are iteration-2 work, not built."
- "It's a message shown to the user recommending they contact L2 — no automated handoff. Wiring
  that to an actual ticketing/queue system is on the roadmap, not built."

---

## Slide 9 — Key Design Decisions & Trade-offs

**Brute-force cosine similarity (no vector database):**
- *Why:* The corpus is ~1,950 chunks from 16 documents — a linear numpy dot-product scan over
  that many vectors runs in well under 50ms. A vector DB would add infrastructure, a compiled
  dependency, and deployment complexity for zero measurable latency benefit at this scale.
- *When this should change:* Once the corpus grows to roughly 50,000-100,000+ chunks (many more
  documents, or documents updated/re-ingested frequently), linear scan latency and memory
  footprint become real constraints — that's the point to introduce a proper vector index.

**No LangChain / LangGraph / CrewAI:**
- *Why:* The orchestration is a fixed, small graph (router → up to 2 specialist agents →
  verification → optional synthesis) — hand-written function calls are easier to read, debug,
  and test than a framework's agent abstraction, and avoid a dependency whose internals the team
  would need to learn and maintain.
- *When this should change:* If the number of distinct tools/agents grows large, or the
  orchestration needs dynamic multi-step planning (not a fixed graph), a framework's tooling for
  that starts to pay for itself — not the case at this scope.

**DuckDB (single embedded file, not a hosted database):**
- *Why:* The structured data is a static export (152,451 PO rows, 2,466 invoices, 13,312 UNSPSC
  rows) — an embedded, single-file analytical database needs zero infrastructure and is fast
  enough (sub-second aggregate queries) at this size.
- *When this should change:* As soon as the data needs to be live (real-time Ariba/SAP feed
  rather than a static export), or needs concurrent writes, or grows beyond what's comfortable in
  a single serverless function's bundle — that's the point to move to a real hosted
  warehouse/database connected to the live source system.

**Vercel serverless (single project, Python functions):**
- *Why:* Appropriate for a prototype with no persistent state requirements, low expected
  request volume, and a desire for the simplest possible one-command deploy.
- *When this should change:* Production traffic volume, need for background jobs (e.g.
  scheduled re-ingestion), sub-request-scoped state, or execution times that risk the platform's
  duration limits are all signals to move to a dedicated backend service with its own compute and
  observability.

**Read-only SQL (regex/keyword-validated, not AST-validated):**
- *Why:* Sufficient because the SQL is generated by a model against a fixed, known schema, not
  submitted directly by an untrusted user — the guard exists to catch generation errors and
  accidental unsafe output, not to defend against an adversarial attacker crafting the input.
- *When this should change:* If this endpoint were ever exposed to less-trusted input (e.g., a
  user-editable prompt that could more directly influence the generated SQL, or if the trust
  boundary changes), an AST-level allowlist (e.g. `sqlglot`) should replace the keyword check as
  defense in depth.

### Speaker notes
- The consistent pattern across all five: match infrastructure complexity to actual current
  scale, and name the specific measurable signal that means it's time to add complexity — not
  "when it gets bigger" vaguely.

### Likely interviewer questions
- "Isn't 'no vector DB' just going to become technical debt?"
- "What's your actual trigger for re-architecting any of this?"

### Suggested answers
- "It's a deliberate choice matched to today's corpus size, with an explicit numeric threshold
  (50-100K chunks) where I'd revisit it — that's different from debt, which implies I didn't
  think about the ceiling."
- Point to the specific "when this should change" line for whichever decision they ask about —
  each one has a concrete trigger, not a vague "at scale."

---

## Slide 10 — Implementation Summary

**Backend:** Python. A single Vercel serverless function (`api/chat.py`, using the Python
runtime's `BaseHTTPRequestHandler` pattern) handling `POST /api/chat`. All agent logic lives in
`api/agents/`: `router.py`, `rag_agent.py`, `data_agent.py`, `qa.py`, `orchestrator.py`,
`store.py` (shared, process-cached access to the vector store and DuckDB connection).

**Frontend:** Next.js 14.2.35 (App Router), React 18.3.1, TypeScript, Tailwind CSS. Client-side
chat interface with sample-question chips, an expandable pipeline-step trace, inline citation
chips, and a collapsible SQL + result-table view. No token-by-token streaming — the API returns
one complete JSON response per turn; the UI shows a cosmetic "thinking" animation while waiting,
then renders the real step-by-step trace and per-step latencies once the response lands.

**Models used (all via the OpenAI API):**
- Chat/reasoning model: `gpt-4o-mini` — used identically for the router, RAG answer generation,
  RAG groundedness judge, SQL generation, SQL result summarization, and the synthesizer.
- Embedding model: `text-embedding-3-small` — used for both document ingestion and query-time
  embedding.

**Deployment:** Single Vercel project. `vercel.json` sets `maxDuration: 60` seconds on the chat
function. The deployed function bundle excludes doc-parsing libraries and raw source
data/scripts (`.vercelignore`) — it only ships the agent code and the pre-built
`api/_store/` artifacts (embeddings, chunk metadata, the DuckDB file).

**Key libraries:**
- Runtime (deployed): `openai` 1.57.4, `numpy` 2.1.2, `duckdb` 1.1.1.
- Offline ingestion only (not deployed): `pypdf` 4.3.1, `python-docx` 1.1.2, `python-pptx`
  0.6.23, `openpyxl` 3.1.5.

**Data flow:**
1. *Offline, one-time:* `scripts/ingest_docs.py` parses the 16 in-scope KnowledgeBase documents,
   chunks them, embeds each chunk, writes `chunks.json` + `embeddings.npy`.
   `scripts/build_duckdb.py` cleans and loads the PO/Invoice CSVs and the UNSPSC reference into a
   single `procurement.duckdb` file. Both outputs are committed to the repo.
2. *At request time:* User question → Router → (RAG path and/or SQL path, per classification) →
   Verification → optional Synthesizer → one JSON response back to the UI.

**No marketing framing** — this is the literal stack, nothing is abstracted into a product name
beyond what's actually running.

### Speaker notes
- Have this slide open (or memorized) if asked "walk me through exactly what's running" — it's
  the fastest way to answer that precisely.

### Likely interviewer questions
- "Why gpt-4o-mini specifically, not GPT-4o or o1?"
- "What's the actual monthly cost of running this?"

### Suggested answers
- "Cost and latency for a chat-facing helpdesk with several LLM calls per question — mini models
  keep both bounded. I'd benchmark a stronger model specifically for final answer quality before
  committing to that trade-off in production."
- Don't fabricate a cost figure — say honestly that no cost tracking/monitoring was built, and
  that's listed as a known limitation (Slide 13).

---

## Slide 11 — Evaluation Framework (implemented, with real results)

**This is implemented, not just planned** — `scripts/evaluate.py` runs a fixed 15-question set
(`eval/eval_questions.json`) through the real orchestrator (the same code path the live app
uses, called directly rather than mocked) and writes results to `eval/eval_results.json`.

**How quality is measured (metrics actually computed):**
- **Router accuracy** — did the router pick the expected category?
- **Retrieval hit-rate** — did the RAG agent's retrieval surface the expected source document,
  measured independently of whether the downstream QA gate kept it (a methodology bug was found
  and fixed here — see below).
- **Policy groundedness pass-rate** — of the policy answers generated, how many passed the
  LLM-judge groundedness gate.
- **Data groundedness pass-rate** — SQL execution success rate (the deterministic check).
- **Refusal correctness** — were out-of-scope questions correctly refused?
- **Answer relevance** — a separate LLM-judge axis (also `gpt-4o-mini`) scoring 1-5: does the
  final answer, including an honest refusal, actually address the question?
- **Latency** — p50/p95 end-to-end pipeline time.

**Test dataset:** 15 questions (`eval/eval_questions.json`), deliberately including hard cases —
the two literal sample questions from the case study brief, a term likely absent from the
corpus (Leveraged Procurement Agreement), a topic with known thin retrieval coverage
(sourcing-event supplier add), and 2 clear out-of-scope questions — not just easy wins.

**Actual results (real, from `eval/eval_results.json`, not illustrative):**

| Metric | Result |
|---|---|
| Router accuracy | 86.7% (13/15) |
| Retrieval hit-rate | 83.3% (5/6 applicable questions) |
| Policy groundedness pass-rate | 57.1% (4/7) |
| Data groundedness pass-rate | 100% (7/7) |
| Refusal correctness | 100% (2/2) |
| Avg. relevance score | 3.8 / 5 |
| Latency | p50 3,636ms / p95 6,830ms |

**Methodology note worth including verbatim:** the first version of this harness measured
retrieval hit-rate against the response's `citations` field, which is only populated when the
downstream QA gate passes — that conflated "did retrieval find the right document" with "did the
answer survive QA," undercounting retrieval quality (50% before the fix, 83.3% after, on
identical underlying retrieval behavior). Fixed by adding a `retrieved_sources` field populated
independently of QA outcome.

**What a production/CI-integrated evaluation harness would add (not yet implemented):**
- A much larger, continuously-growing question set (real user questions + labels, not just 15
  hand-written ones).
- Running automatically on every prompt/model/schema change (CI gate), not manually on demand.
- Human-reviewed labels for a sample of live traffic, not just synthetic eval questions.
- Tracking metric drift over time, not just a point-in-time snapshot.
- A user feedback signal (e.g. thumbs up/down) feeding back into the eval set — not built.

### Speaker notes
- This is your strongest slide for demonstrating "hands-on GenAI capability" specifically,
  since the case study explicitly asks for it — don't rush past the methodology-bug paragraph,
  it's evidence of rigor, not a confession.

### Likely interviewer questions
- "57% groundedness pass-rate sounds bad — why present that?"
- "Is 15 questions enough to trust these numbers?"

### Suggested answers
- "It's the honest number for a light-RAG scope on real, messy documents — including one with an
  actual unresolved placeholder in it. The point of the QA gate is exactly to convert that 43%
  into safe refusals instead of wrong answers, which the data-groundedness and refusal-
  correctness numbers show it's doing. I'd rather show this than a cherry-picked question set
  that hits 100%."
- "No — 15 questions gives a directional read, not a statistically confident one. That's exactly
  why 'a much larger, continuously-growing question set' is the first thing listed as a
  production gap, not a nice-to-have."

---

## Slide 12 — Roadmap

**Prototype (built now):**
- Router → RAG agent / SQL agent → verification gate → optional synthesizer.
- Static KnowledgeBase document export + static PO/Invoice/UNSPSC data export.
- No authentication — single shared L1 desk.
- Live deployed demo.
- Working 15-question offline eval harness with real results.

**Pilot (next):**
- Multi-turn conversation memory (follow-up questions).
- Live Ariba/SAP/Icertis API integration, replacing static exports.
- **SQL answer verification** — semantic/numeric correctness checking beyond "did it execute,"
  e.g. a second model cross-checking generated SQL logic against the question, or a small
  hand-verified reference-query set to sanity-check against. *(Explicitly called out per your
  instruction — this is the single most important gap to close before any real usage.)*
- Actual escalation integration (ticket/queue handoff), not just a recommendation message.
- User feedback capture (thumbs up/down) feeding the eval set.
- A materially larger eval question set, ideally sourced from real usage.
- Automated UNSPSC classification suggestions for new line items.
- Query timeout enforcement on the SQL path.

**Enterprise (scale):**
- SSO + department/role-scoped data access.
- PII/financial guardrails.
- Human-in-the-loop review path for low-confidence answers, not just a text recommendation.
- CI-integrated, continuously-run evaluation pipeline (see Slide 11).
- Production monitoring/observability (logging, alerting, cost tracking) — none exists today.
- AST-level SQL validation (e.g. `sqlglot`) replacing the keyword-based guard.
- A real vector index, once corpus size crosses the ~50-100K chunk threshold.
- Multi-language support.
- Cost and latency optimization (caching, a smaller routing model).

### Speaker notes
- Put SQL answer verification first in the Pilot column when presenting out loud — it's the gap
  most likely to be probed given the emphasis in this deck, and leading with it shows you
  already know it's the priority.

### Likely interviewer questions
- "If you had one more week, what would you build first?"
- "What's the single biggest risk in the current system?"

### Suggested answers
- "SQL answer verification, without question — it's the one place a wrong answer could currently
  reach a user with high confidence, because execution succeeding doesn't mean the logic is
  right."
- Same answer, framed as risk rather than priority — they're the same gap.

---

## Slide 13 — Known Limitations

Stated plainly, no softening:

- **No authentication.** Single shared L1 desk, no user identity, no per-user/department data
  scoping.
- **Static documents and static structured data.** No live connection to Ariba/SAP/Icertis —
  everything is the export provided with the case study.
- **Small corpus.** ~1,950 chunks from 16 documents — fine at this scale, a real constraint if
  the corpus grows substantially without revisiting the retrieval approach (see Slide 9).
- **No production monitoring.** No logging/alerting/cost-tracking/observability beyond what
  Vercel provides by default.
- **Evaluation harness exists but is small and manual.** 15 questions, run on demand, not
  integrated into CI, not continuously growing from real usage (see Slide 11 for what exists
  vs. what a production version needs).
- **SQL answer verification only checks execution success, not correctness.** The deterministic
  check cannot detect a query that runs without error but answers a different question than the
  one asked. Semantic/numeric correctness verification is not implemented.
- **No live ERP integration.** No connection to real SAP Ariba, Icertis, or any live procurement
  system.
- **No conversation memory.** Every question is handled statelessly; no multi-turn context.
- **No actual escalation mechanism.** "Escalate to L2" is a message shown to the user, not an
  integration with any ticketing or queue system.
- **SQL Safety Guard is keyword/regex-based, not AST-validated.** Sufficient for the current
  trust boundary (model-generated SQL against a fixed schema), not a substitute for AST-level
  validation if that boundary changes.
- **No query timeout enforcement on the SQL path**, beyond the auto-applied row `LIMIT`.
- **Retrieval recall is imperfect.** Confirmed on the eval set (83.3% hit-rate) and via direct
  investigation — some genuinely relevant content in the corpus doesn't reliably surface in the
  top-6 similarity results, due to naive (non-structure-aware) chunking.
- **No rate limiting or abuse protection** on the API endpoint.
- **Router misclassification is possible and measured** (86.7% accuracy on the eval set) — a
  misrouted question silently gets the wrong agent(s), not a graceful degraded answer.

### Speaker notes
- Read this list essentially verbatim if asked "what would you tell a skeptical reviewer" — it's
  deliberately written to not need euphemism.

### Likely interviewer questions
- "Which of these worries you most?"
- "Is this ready for even a limited pilot as-is?"

### Suggested answers
- "SQL answer verification and no live ERP integration, in that order — the first is a
  correctness risk, the second means nothing here reflects current reality yet."
- "Not without at least SQL answer verification and some form of escalation integration — those
  two are the minimum bar before I'd put this in front of real requesters, even in a limited
  pilot."

---

## Slide 14 — Conclusion

**Business value:** Demonstrates a working pattern for deflecting repetitive procurement L1
questions — both policy lookups and structured spend/PO analytics — through one interface, with
answers that cite their sources and explicitly decline to guess when they can't verify
themselves. No ROI is claimed; that requires real usage data this prototype doesn't have.

**Technical value:** A working, deployed, evaluated multi-agent system built end-to-end in a
single time-boxed session — router, RAG, text-to-SQL with a safety guard, a two-strategy
verification layer, and a real (if small) evaluation harness with honestly-reported results,
including one found-and-fixed methodology bug in the eval harness itself.

**Future evolution:** The roadmap (Slide 12) is explicit about what separates this prototype from
something pilot-ready — most importantly, SQL answer-correctness verification, live system
integration, and a larger/continuous evaluation loop. None of these are architecturally blocked
by the current design; they're additive next steps on top of it.

### Speaker notes
- Close on the throughline from Slide 1: this system's defining property is that it knows what
  it doesn't know, and says so — end on that, not on a feature list.

### Likely interviewer questions
- "If we greenlit a pilot tomorrow, what's the very first thing you'd do?"

### Suggested answers
- "Two things in parallel: build SQL answer-correctness verification, and start capturing real L1
  ticket data so the next eval set and the ROI case are both grounded in actual usage instead of
  a 15-question synthetic set."
