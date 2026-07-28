"""Router agent: one LLM call that classifies the query before any retrieval happens."""

from langchain_core.prompts import ChatPromptTemplate

from .contracts import RouterDecision
from .store import get_chat_model

# Escaped for LangChain's f-string-style template renderer ({{ }} -> literal { }
# on render, same convention Python's str.format() already uses) -- the rendered
# system message sent to the model is byte-identical to the original literal text.
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

Respond with strict JSON: {{"category": "POLICY|DATA|BOTH|OUT_OF_SCOPE", "reasoning": "<one \
short sentence>"}}"""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{query}"),
    ]
)


def route(query: str) -> dict:
    chain = _prompt | get_chat_model().with_structured_output(
        RouterDecision, method="json_schema", strict=True
    )
    try:
        decision = chain.invoke({"query": query})
    except Exception:
        # Structured-output/validation failure -- same safe default the original
        # manual "category not in (...)" membership check used to fall back to.
        decision = RouterDecision(category="OUT_OF_SCOPE", reasoning="")
    return {"category": decision.category, "reasoning": decision.reasoning}
