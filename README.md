# Procurement Copilot — L1 AI Helpdesk

Case study submission for the Sr. Procurement AI & Analytics Lead role (REQ-10069230).

**Live demo:** https://novartis-assignment.vercel.app
**Design doc (architecture + tradeoffs):** [DESIGN.md](DESIGN.md)
**Eval results:** [eval/eval_results.json](eval/eval_results.json)

## Problem

Build a Level 1 procurement helpdesk that can answer questions from a pharma company's
procurement policy documents (PDF/DOCX/PPTX/XLSX) and its structured SAP Ariba spend/PO/invoice
data — a single chat interface instead of "read 16 PDFs and query a spreadsheet yourself."

## What's built (Iteration 1)

A multi-agent pipeline: a router classifies each question, a RAG agent answers from the policy
KnowledgeBase, a text-to-SQL agent answers from the PO/Invoice/UNSPSC data, and a QA gate checks
groundedness before either answer reaches the user — falling back to an honest "escalate to L2"
rather than guessing. See [DESIGN.md](DESIGN.md) for the full architecture and every tradeoff
behind it.

## Product plan

- **Iteration 1 (built now):** Multi-agent chat over the static KnowledgeBase export and static
  PO/Invoice CSVs. Router → RAG agent / SQL agent → groundedness QA gate → safe fallback. No auth
  (single shared L1 desk, no per-user data scoping needed yet). Deployed, live demo. Offline eval
  harness with a 15-question set.
- **Iteration 2:** Multi-turn conversational memory (follow-up questions); live Ariba/SAP/Icertis
  API integration instead of static exports; automated UNSPSC classification suggestions for new
  line items; supplier-onboarding workflow triggers (not just "how do I," but actually doing it);
  thumbs-up/down feedback capture feeding back into the eval set; proactive spend-anomaly alerts.
- **Iteration 3:** SSO + department/role-scoped data access; PII/financial guardrails; human-in-
  the-loop escalation to L2 procurement with full pipeline context attached; continuous automated
  eval/regression pipeline on every prompt/model change; cost and latency optimization (caching,
  a smaller routing model); multi-language support.

## Repo layout

```
data/KnowledgeBase/       policy PDFs/DOCX/PPTX/XLSX (source docs, minus one 68MB off-topic PDF)
data/Structured_Data/     PO CSV, Invoice CSV, UNSPSC reference
scripts/                  offline ingestion + eval scripts (not deployed)
api/agents/               router, rag_agent, data_agent, qa, orchestrator (the actual "solution")
api/chat.py               Vercel Python function entrypoint (POST /api/chat)
api/_store/                committed embeddings.npy / chunks.json / procurement.duckdb
app/                       Next.js chat UI
eval/                      eval question set + results
```

## Running locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r scripts/requirements-ingest.txt
echo "OPENAI_API_KEY=sk-..." > .env.local

# one-time: build the RAG store and structured-data DB (already committed, but to rebuild)
python3 scripts/build_duckdb.py
python3 scripts/ingest_docs.py

# run the eval harness
python3 scripts/evaluate.py

# run the app (frontend + Python API)
npm install
vercel dev
```

## Deploying

```bash
vercel link
vercel env add OPENAI_API_KEY production   # paste the key when prompted
vercel --prod
```
