"""Router agent: one LLM call that classifies the query before any retrieval happens."""

import json

from .store import CHAT_MODEL, get_client

SYSTEM_PROMPT = """You are the routing agent for a Level 1 procurement helpdesk chatbot at a \
pharmaceutical company. The company runs SAP Ariba for its procurement processes and has \
historical Purchase Order (PO) and Invoice data.

Classify the user's question into exactly one category:

- "POLICY": needs company procurement policy, process, or systems knowledge (e.g. contract vs. \
PO rules, spend thresholds, Ariba/supplier-portal how-tos, sourcing events, supplier lifecycle, \
UNSPSC classification concepts, contract compliance).
- "DATA": needs analysis over historical structured data (spend by department/supplier, PO \
counts, invoice amounts, UNSPSC code lookups, payment/settlement timing).
- "BOTH": genuinely needs both a policy/process answer AND a data lookup to fully answer (e.g. \
"do I need a contract for a $70k laptop purchase" needs both the threshold policy AND the \
correct UNSPSC classification/threshold lookup).
- "OUT_OF_SCOPE": unrelated to procurement policy, procurement systems, or procurement/spend data.

Respond with strict JSON: {"category": "POLICY|DATA|BOTH|OUT_OF_SCOPE", "reasoning": "<one \
short sentence>"}"""


def route(query: str) -> dict:
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
    )
    result = json.loads(resp.choices[0].message.content)
    category = result.get("category", "OUT_OF_SCOPE").upper()
    if category not in ("POLICY", "DATA", "BOTH", "OUT_OF_SCOPE"):
        category = "OUT_OF_SCOPE"
    return {"category": category, "reasoning": result.get("reasoning", "")}
