"""Planner -- Step 3A: bounded planner-based tool dispatch, not an
autonomous agent loop.

One LLM call decides WHICH of a fixed, small set of capabilities (bounded
tools) a request needs. The planner does not decide execution order, does
not invoke tools itself, and does not loop or retry -- it selects a set of
required capabilities; canonicalize_tools() (pure, deterministic, no LLM)
dedupes that set and fixes it into the graph's required execution order
(policy before data), and derive_category() maps the canonical set onto the
same four-value category the router used to return directly, so the
response contract's `category` field is unchanged.

Failure handling: `route()`'s original try/except-free json.loads() would
crash the whole request on a malformed LLM response. plan() catches any
structured-output/validation exception and falls back to tools_to_call=[]
(the same safe default), but -- unlike a silent fallback -- it also records
`planner_failed=True` and the exception text, so a genuine "this question is
out of scope" decision from the model is never indistinguishable from an
LLM/infrastructure failure that degraded to the same empty tool list.
"""

from langchain_core.prompts import ChatPromptTemplate

from .contracts import PlannerDecision
from .store import get_chat_model

CANONICAL_TOOL_ORDER = ("policy_answer", "procurement_data_answer")

_CATEGORY_BY_CANONICAL_TOOLS = {
    (): "OUT_OF_SCOPE",
    ("policy_answer",): "POLICY",
    ("procurement_data_answer",): "DATA",
    ("policy_answer", "procurement_data_answer"): "BOTH",
}

SYSTEM_PROMPT = """You are the planning agent for a Level 1 procurement helpdesk chatbot at a \
pharmaceutical company. The company runs SAP Ariba for its procurement processes and has \
historical Purchase Order (PO) and Invoice data.

Decide which capabilities are needed to fully answer the user's question. There are two \
available capabilities:

- "policy_answer": needs company procurement policy, process, or systems knowledge (e.g. contract \
vs. PO rules, spend thresholds, Ariba/supplier-portal how-tos, sourcing events, supplier \
lifecycle, UNSPSC classification concepts and hierarchy, contract compliance).
- "procurement_data_answer": needs analysis over historical structured data (spend by \
department/supplier, PO counts, invoice amounts, UNSPSC code lookups, payment/settlement timing).

Rules:
- If the question is about procurement policy, procurement systems, or procurement/spend/PO/\
invoice data in ANY way, select at least one capability -- do not select none just because you're \
unsure which one fits best.
- Select BOTH when the question genuinely needs a policy/process answer AND a data lookup to be \
fully answered (e.g. "do I need a contract for a $70k laptop purchase" needs both the threshold \
policy AND the correct UNSPSC classification/threshold lookup).
- Select neither ONLY if the question is unrelated to procurement policy, procurement systems, or \
procurement/spend data altogether.
- The order you list capabilities in does not matter.

Respond with strict JSON: {{"tools_to_call": ["policy_answer", "procurement_data_answer"], \
"reasoning": "<one short sentence>"}}"""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        ("human", "{query}"),
    ]
)


def canonicalize_tools(tools: list) -> list:
    """Dedupe and fix into the required deterministic execution order
    (policy before data). Silently drops anything not in
    CANONICAL_TOOL_ORDER -- defense in depth; PlannerDecision's Literal
    typing should already guarantee this, but this function is a pure,
    standalone unit that shouldn't have to trust its caller."""
    requested = {t for t in tools if t in CANONICAL_TOOL_ORDER}
    return [t for t in CANONICAL_TOOL_ORDER if t in requested]


def derive_category(canonical_tools: list) -> str:
    return _CATEGORY_BY_CANONICAL_TOOLS[tuple(canonical_tools)]


def plan(query: str) -> dict:
    chain = _prompt | get_chat_model().with_structured_output(
        PlannerDecision, method="json_schema", strict=True
    )
    try:
        decision = chain.invoke({"query": query})
        raw_tools = decision.tools_to_call
        reasoning = decision.reasoning
        planner_failed = False
        planner_error = None
    except Exception as e:
        raw_tools = []
        reasoning = ""
        planner_failed = True
        planner_error = str(e)

    tools = canonicalize_tools(raw_tools)
    category = derive_category(tools)

    return {
        "tools_to_call": tools,
        "category": category,
        "reasoning": reasoning,
        "planner_failed": planner_failed,
        "planner_error": planner_error,
    }
