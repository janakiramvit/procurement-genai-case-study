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

from . import memory
from .contracts import PlannerAction, PlannerDecision
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


# ---------------------------------------------------------------------------
# Step 3B: bounded plan -> act -> observe agent loop. plan_next_action()
# decides ONE next step at a time (CALL_TOOL a specific capability, or
# FINISH), conditioned on this turn's real observations so far -- unlike
# plan() above, which commits to a full set of capabilities upfront and never
# sees a tool's result. Execution order/budget enforcement is NOT this
# function's job (see graph_v2.py); this is purely "what's the next step."
# ---------------------------------------------------------------------------

AGENT_SYSTEM_PROMPT = """You are the planning agent for a Level 1 procurement helpdesk chatbot at a \
pharmaceutical company. The company runs SAP Ariba for its procurement processes and has \
historical Purchase Order (PO) and Invoice data.

You operate in a bounded plan-act-observe loop. Each time you're asked, decide the SINGLE next \
step: call one specific capability, or FINISH if you already have sufficient grounded evidence \
from THIS TURN's tool observations to fully and accurately answer the user's current question.

Two available capabilities:
- "policy_answer": needs company procurement policy, process, or systems knowledge -- including \
questions about approval requirements, tender requirements, contract requirements, procurement \
thresholds, sourcing rules, or compliance rules (e.g. contract vs. PO rules, spend thresholds, \
Ariba/supplier-portal how-tos, sourcing events, supplier lifecycle, UNSPSC classification \
concepts and hierarchy, contract compliance).
- "procurement_data_answer": needs analysis over historical structured data (spend by \
department/supplier, PO counts, invoice amounts, UNSPSC code lookups, payment/settlement timing).

IMPORTANT -- conversation history vs. evidence:
Prior conversation turns below are provided ONLY to help you understand what the user is \
currently asking about (e.g. resolving "it" / "that purchase" / "them" to a specific supplier, \
category, or amount mentioned earlier in this session). A prior assistant answer is NOT verified \
evidence for the CURRENT turn -- even if a fact was stated earlier, you must obtain current, \
grounded evidence via a tool call this turn if the current question needs it. Never answer purely \
from what a previous assistant message said; use history only to resolve what the question refers \
to, then get fresh evidence.

Rules for calling a tool:
- Call "policy_answer" before FINISHing whenever the question asks about an approval requirement, \
tender/RFP requirement, contract requirement, procurement threshold, sourcing rule, or compliance \
rule for a specific purchase, supplier, or spend decision -- do not FINISH with zero observations \
just because you are unsure, and do not answer the question yourself from general knowledge.
- Never resolve a compliance/approval/permission question ("can we...", "do we need...", "is this \
allowed...", "are we required to...") from your own reasoning. You only decide which capability \
retrieves relevant evidence -- the actual answer, and whether the evidence supports it, is \
determined by the tool's retrieval and the downstream verification step, not by you.
- Do NOT call a tool merely because a question mentions "procurement" or "procurement systems" in \
passing. Questions about building, creating, automating, or integrating a system or tool (e.g. \
"can we build a procurement dashboard", "can we automate invoice matching", "can we integrate SAP \
with procurement systems") are product/engineering feasibility questions, not policy or data \
questions -- neither capability can answer them. FINISH with zero tool calls for these, unless \
they also separately ask about an approval, tender, contract, threshold, sourcing, or compliance \
requirement for a specific purchase, supplier, or spend decision.
- Call a tool only for genuinely missing information that this turn's observations don't already \
cover.
- You may call the SAME tool more than once ONLY if a new observation this turn creates a \
meaningfully different, more specific input (e.g. you learned the purchase amount and now need \
the policy answer for that specific amount). Do not call the same tool again with substantially \
the same input -- that wastes budget and will be blocked.
- If your most-recent action was BLOCKED (duplicate or per-tool-limit) or its evidence FAILED the \
groundedness/validation check, do NOT propose the same tool with equivalent input again. Instead, \
either call a genuinely different capability that could add new evidence, or FINISH with whatever \
evidence you have.
- FINISH with the observations already gathered as soon as they are sufficient. Do not keep going \
"to be thorough" once you already have what's needed.
- FINISH with ZERO tool calls only when the question is clearly outside the procurement domain \
altogether, or no available capability could plausibly supply relevant evidence for it.

Conversation history (context for reference resolution only, NOT evidence):
{conversation_history}

Actions taken this turn so far:
{actions_taken}

Observations so far this turn:
{observations}

Remaining budget: {remaining_decisions} planner decisions left, {remaining_tool_calls} tool \
calls left (max 3 executions per individual capability).

Respond with strict JSON: {{"action": "CALL_TOOL"|"FINISH", "tool": "policy_answer"|\
"procurement_data_answer"|null, "input": "<specific question to send the tool>"|null}}"""

_agent_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", AGENT_SYSTEM_PROMPT),
        ("human", "{query}"),
    ]
)


def _render_actions_taken(actions_taken: list) -> str:
    if not actions_taken:
        return "(none yet)"
    lines = []
    for a in actions_taken:
        if a["action"] == "FINISH":
            lines.append(f"{a['decision_number']}. FINISH")
        else:
            lines.append(f"{a['decision_number']}. CALL_TOOL {a['tool']} with input: {a['input']!r}")
    return "\n".join(lines)


def _render_observations(observations: list) -> str:
    if not observations:
        return "(none yet)"
    lines = []
    for o in observations:
        qa_note = ""
        if o.get("qa_passed") is not None:
            qa_note = f" [groundedness check: {'PASSED' if o['qa_passed'] else 'FAILED'}]"
        summary = (o.get("answer_summary") or "")[:400]
        lines.append(f"- {o['tool']} ({o['status']}){qa_note}: {summary}")
    return "\n".join(lines)


def plan_next_action(
    query: str,
    conversation_history: list,
    actions_taken: list,
    observations: list,
    remaining_decisions: int,
    remaining_tool_calls: int,
) -> dict:
    chain = _agent_prompt | get_chat_model().with_structured_output(
        PlannerAction, method="json_schema", strict=True
    )
    try:
        action = chain.invoke(
            {
                "query": query,
                "conversation_history": memory.render_history_for_prompt(conversation_history),
                "actions_taken": _render_actions_taken(actions_taken),
                "observations": _render_observations(observations),
                "remaining_decisions": remaining_decisions,
                "remaining_tool_calls": remaining_tool_calls,
            }
        )
        # Cross-field validation, never trusted to the schema alone (same discipline as
        # every other structured-output contract in this codebase): CALL_TOOL requires
        # both tool and input; anything inconsistent is treated as a planner failure.
        if action.action == "CALL_TOOL" and (not action.tool or not action.input):
            raise ValueError("CALL_TOOL action missing required tool/input")
        planner_failed = False
        planner_error = None
    except Exception as e:
        action = PlannerAction(action="FINISH", tool=None, input=None)
        planner_failed = True
        planner_error = str(e)

    return {"action": action, "planner_failed": planner_failed, "planner_error": planner_error}
