# Design Document — Procurement Copilot

## 1. Architecture

```
User question
     │
     ▼
 ┌─────────┐   POLICY / DATA / BOTH / OUT_OF_SCOPE
 │ Router  │───────────────────────────────────────┐
 └─────────┘                                        │
     │                                               │
     ▼ (POLICY / BOTH)                    ▼ (DATA / BOTH)
 ┌───────────┐                        ┌───────────────┐
 │ RAG Agent │                        │  Data Agent    │
 │ retrieve  │                        │  text-to-SQL   │
 │ top-k +   │                        │  + guardrails  │
 │ answer    │                        │  + execute     │
 └───────────┘                        └───────────────┘
     │                                        │
     ▼                                        ▼
 ┌────────────────────┐          ┌─────────────────────────┐
 │ QA: LLM-judge       │          │ QA: deterministic        │
 │ groundedness check  │          │ (did SQL execute OK?)    │
 └────────────────────┘          └─────────────────────────┘
     │                                        │
     └──────────────┬─────────────────────────┘
                     ▼
         pass+pass → Synthesizer (BOTH only)
         any fail  → safe fallback ("escalate to L2")
                     ▼
              Structured response
       (answer, citations, SQL, per-step
        latency, groundedness verdicts)
```

One Next.js app deployed to Vercel: a React chat UI plus Python serverless functions under
`/api` for all retrieval/agent/QA logic — satisfies "implement the solution in Python" while
giving a single, clean, demoable deploy.

## 2. Data layer

### 2.1 Unstructured docs → RAG store
`scripts/ingest_docs.py` parses all 16 in-scope KnowledgeBase files (PDF via `pypdf`, DOCX via
`python-docx`, PPTX via `python-pptx`), does character-based sliding-window chunking (~600
tokens, ~100 token overlap, snapped to whitespace), embeds each chunk with
`text-embedding-3-small`, and writes `chunks.json` + `embeddings.npy`.

**Excluded `power-bi-personas-business-user.pdf` (68MB)** — it's about Power BI personas, not
procurement, and would have been pure noise in the vector store. A deliberate filtering
decision, not an oversight.

**Query-time retrieval is brute-force numpy cosine similarity, not a vector DB (FAISS/Chroma/
Pinecone).** With ~1,950 chunks a linear scan is <50ms — a vector index would add deployment
complexity (compiled dependencies, index files, possible size limits on serverless) for zero
latency benefit at this corpus size. This is an explicit scale-limited tradeoff: fine to roughly
50-100k chunks; past that, iteration 2 would need a real vector DB (and probably a managed one,
since Vercel functions have no persistent local disk).

**UNSPSC codes are NOT embedded as RAG text.** The UNGM UNSPSC reference file is a 13,313-row
hierarchical code/title lookup table, not prose. Loaded into DuckDB as a queryable table instead
— exact/`ILIKE` matching on code or title is categorically more reliable for a taxonomy lookup
than embedding similarity (e.g. a user asking about "laptops" needs the SQL agent to know the
UNSPSC title is "Notebook computers," which is a lookup/synonym problem, not a semantic-
similarity problem).

### 2.2 Structured data → DuckDB
`scripts/build_duckdb.py` loads `purchase_orders_2012_2015.csv`, `Invoice_data.csv`, and the
UNSPSC xlsx into one committed `procurement.duckdb` file (~18.5MB), with:
- **snake_case column names** (no spaces) so the text-to-SQL agent generates valid SQL without
  identifier quoting — this measurably reduces LLM SQL-generation errors versus keeping the
  original `"Purchase Order Number"`-style headers.
- **Types cleaned at build time, not query time** (currency strings like `"$1,380.54 "` parsed
  to `DOUBLE`, US-format dates parsed to `DATE`) so every query the SQL agent issues later is a
  fast SELECT over already-typed columns, not a query full of ad hoc casting the LLM would have
  to get right every time.
- **A single embedded file, no external database/infra** — appropriate for a take-home with
  static CSV exports; iteration 2 would point this at the live Ariba/SAP data warehouse instead.

**Real data-quality finding, not a hypothetical one:** `wc -l` on the PO CSV reports 376,876
lines, and the data dictionary describes it as "~376,876 rows." That's wrong — the `Location`
column embeds literal newlines inside quoted values (e.g. `"90640\n(34.01573, -118.113367)"`),
so a single logical CSV record can span several physical lines. I verified the true row count
(~152,451) by cross-checking DuckDB's parse against Python's own stdlib `csv` module — they
agree to within 14 rows (the file has 9 genuinely corrupted records with unterminated quotes,
which are skipped and logged). This mattered: naively trusting `ignore_errors` without
`store_rejects=True` silently dropped ~17k additional *valid* rows to a DuckDB CSV-reader resync
quirk — caught by comparing row counts against the independent stdlib parse rather than assuming
the first successful-looking run was correct.

**`Pharma_UNSPSC_Thresholds.pdf` had a corrupted trailer** (`/Root` pointed to an object number
that doesn't exist; the Catalog's own `/Pages` self-referenced instead of pointing at the real
page tree) — both pypdf and PyMuPDF refused to open it. This is exactly the file with
per-country USD spend thresholds, directly relevant to "do I need a contract for a $70k
purchase"-style questions, so it was worth a targeted fix rather than a silent skip:
`ingest_docs.py` detects this specific off-by-one corruption pattern and patches the two object
references before retrying. General-purpose PDF repair would be overkill; a narrow, documented
patch for a known corruption shape is not.

## 3. Multi-agent pipeline

**Deterministic router graph, not an autonomous agent loop.** The router makes one classification
call, then a fixed, known sequence of agents runs based on that classification — the pipeline
never lets a model decide its own tool sequence. For a scoped L1 helpdesk this beats an
autonomous loop (e.g. LangGraph/AutoGPT-style free tool selection) on every axis that matters
here: latency (no exploratory tool-call loops), cost (bounded number of LLM calls per question,
known up front), predictability (the same question always takes the same code path, which
matters for debugging and for the eval harness), and safety (no risk of the model deciding to
run some other tool in an unexpected order). The tradeoff is flexibility — a genuinely
open-ended assistant would need more autonomy — but that's not what an L1 helpdesk is.

**Separate specialized agents instead of one mega-prompt with the full schema + doc corpus
stuffed into context.** A single prompt carrying both the 30-column PO schema and the full
policy corpus would be slower, more expensive per call, and more prone to the model ignoring the
right source when only one is actually relevant. Splitting router → specialist agent means each
LLM call sees only the context it needs.

**Text-to-SQL with guardrails, not a pandas/code-execution agent.** The data agent generates SQL
(validated: single `SELECT`/`WITH` statement, no DDL/DML/pragma/attach keywords, no statement
chaining, auto-`LIMIT`) and runs it against a `read_only=True` DuckDB connection. This is a
regex/keyword allowlist, not a full SQL parser — acceptable because the SQL is model-generated
against a fixed, known schema rather than raw untrusted user input, but a production version
would add an AST-level allowlist (e.g. `sqlglot`) as defense in depth. The alternative — letting
the model write and execute arbitrary Python/pandas — has a much larger attack surface for a
helpdesk that doesn't need it.

## 4. QA / groundedness — the core focus area

Different agents need different verification strategies, and using the same strategy for both
would be worse on both axes:

- **RAG answers are free text generated from retrieved passages.** Groundedness has to be
  *judged* — an LLM-judge checks whether every claim in the answer is actually supported by the
  passages it cites, scores 1-5, and passes only at ≥4.
- **SQL answers are generated from the query's own execution result.** Ground truth is directly
  available, so a **deterministic** check (did the SQL execute without error, did it return
  rows) is both cheaper and more reliable than asking a second LLM to "judge" a fact it could
  just as easily verify by re-reading the result set it already has.

Either failure mode returns a safe fallback ("I couldn't verify a reliable answer... escalate to
L2") instead of a hallucinated one.

**This isn't a theoretical design point — it caught a real issue during development.** The
question "I want to buy laptops in USA for USD 70k, do I need a contract or a PO?" retrieves
`Procurement_Guidelines.pptx` slide 19, which says *"Value above $[C]"* — the source deck itself
ships with an unresolved template placeholder where a real dollar threshold should be. The RAG
agent (correctly) cited this passage, generated an answer referencing "$[C]," and the
groundedness judge correctly refused to accept that as a real number, failing the answer instead
of letting a fabricated-sounding threshold reach the user. That is exactly the failure mode this
QA gate exists to catch, and it did.

## 5. Deployment — decisions and what actually broke

**No token-by-token streaming from the Python API.** The API returns one complete structured
response (router decision, per-agent output, groundedness verdicts, latency per step) rather
than streaming tokens over SSE. This was a time-budget call: SSE from a Python function on
Vercel adds real complexity, and for a 5-hour build the payoff wasn't worth it. Instead the UI
renders a visible multi-step pipeline trace once the response lands, cosmetically animating
through the real stage names while waiting. Net effect: for demonstrating a multi-agent + QA
architecture specifically, this arguably reads *better* than raw token streaming would have,
even though it isn't "real" progressive disclosure.

**Vercel Python function size limit (225MB) was blown on the first deploy attempt (324MB).**
Root cause: `requirements.txt` listed the doc-parsing libraries (`pypdf`, `python-docx`,
`python-pptx`, `openpyxl`) needed by the *offline ingestion scripts*, and Vercel's builder
bundles every dependency in `requirements.txt` into the deployed function regardless of whether
`api/chat.py` actually imports it. Those libraries pull in `lxml` (20MB) and `PIL` (14MB)
transitively. Fix: moved them to `scripts/requirements-ingest.txt` (deliberately *not* named
`requirements.txt`, since Vercel appears to auto-discover and merge every file with that exact
name anywhere in the repo — a second attempt with a nested `requirements.txt` reproduced the
identical 324MB bundle). The deployed function now only needs `openai`, `numpy`, `duckdb`.

**`ModuleNotFoundError: No module named 'agents'` in production, despite working locally.**
Vercel's Python runtime imports `api/chat.py` via `importlib` rather than a normal `python
chat.py` invocation, so the file's own directory isn't automatically added to `sys.path` the way
it would be for a plain script run — the sibling `api/agents/` package wasn't importable. Fixed
with an explicit `sys.path.insert(0, ...)` at the top of `chat.py`. This only surfaced once
deployed; local `import` testing via a plain Python REPL didn't reproduce it, which is a good
argument for testing against real deployment infrastructure early rather than assuming local
success generalizes.

## 6. Known limitations (honest, not hidden)

- **RAG retrieval recall is imperfect on some questions.** "How do I add a supplier to a
  sourcing event" has genuinely relevant content in the corpus (confirmed by direct keyword
  search), but it's diluted among noisy table-of-contents-style chunks and doesn't reliably make
  the naive top-6 similarity cut. This is a chunking-quality problem (no structural awareness of
  headers/TOC vs. body text), not a missing-content problem. Per the "light RAG" scope for this
  build, this is documented rather than chased with reranking/structure-aware chunking — that's
  the iteration-2 move.
- **Some terms genuinely aren't covered by the KnowledgeBase corpus** (e.g. "Leveraged
  Procurement Agreement" appears in the PO data dictionary but isn't explained in any ingested
  document). The system should — and in eval testing, does — refuse honestly here rather than
  guess from general LLM knowledge.
- **The regex-based SQL guardrail is not a full parser.** Sufficient for model-generated SQL
  against a fixed schema; not a substitute for an AST-level allowlist if this were ever exposed
  to less-trusted input.
- **Single-turn only.** No conversation memory across turns yet — each question is handled
  independently. See Iteration 2 in the README.

## 7. Evaluation methodology

`scripts/evaluate.py` runs a fixed 15-question set (`eval/eval_questions.json`) through the real
orchestrator (not a mocked pipeline) and reports:

| Metric | Result | What it measures |
|---|---|---|
| Router accuracy | 86.7% (13/15) | Did the router pick the right category? |
| Retrieval hit-rate | 83.3% (5/6 applicable) | Did the RAG agent's retrieval surface the expected source doc, independent of downstream QA |
| Policy groundedness pass-rate | 57.1% (4/7) | Of policy answers generated, how many passed the LLM-judge groundedness gate |
| Data groundedness pass-rate | 100% (7/7) | SQL execution success rate (deterministic) |
| Refusal correctness | 100% (2/2) | Out-of-scope questions correctly refused |
| Avg. relevance | 3.8 / 5 | Separate LLM-judge axis: does the final answer (including safe refusals) actually address the question |
| Latency | p50 3.6s / p95 6.8s | End-to-end pipeline latency |

The question set was deliberately built to include hard cases, not just easy wins: the two
ReadMe sample questions, a term likely absent from the corpus (LPA), a topic with known thin
retrieval coverage (sourcing-event supplier add), and 2 clear out-of-scope questions. The 57%
policy groundedness pass-rate looks unflattering in isolation, but it's the honest number for a
"light RAG" scope on real, messy source documents (including one with an actual unresolved
placeholder in it) — and the QA gate converting those failures into safe refusals rather than
wrong answers is the entire point of this design. A production iteration would push this number
up via better chunking/retrieval (see §6), not by loosening the QA gate.

**One methodology bug found and fixed while building this harness, worth noting for its own
sake:** the orchestrator only populated the response's `citations` field when the QA gate
passed, so the eval script's first pass measured retrieval hit-rate against citations and got
50% — conflating "did retrieval find the doc" with "did the answer survive QA." Added a
`retrieved_sources` field that's always populated when the RAG agent runs, independent of QA
outcome, which corrected the measured retrieval hit-rate to 83.3% on identical underlying
behavior. Worth flagging because it's a realistic example of an eval harness measuring the wrong
thing by accident, not a contrived one.
