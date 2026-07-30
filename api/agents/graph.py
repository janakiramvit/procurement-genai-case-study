"""LangGraph parent graph -- Step 1, extended in Step 3A.

Step 3A is bounded planner-based tool dispatch, not an autonomous agent
loop: planner_node makes one bounded LLM call selecting which of two fixed
capabilities (policy_answer, procurement_data_answer) a request needs;
execution order is fixed in code (planner.canonicalize_tools -- policy
always before data), not decided by the planner or the graph at runtime.
Same sequential control flow as Step 1, same response contract -- only the
decision node and the two capability nodes' names changed.

Node execution order per category (identical to Step 1's pipeline, now
driven by canonical tool-list membership instead of a category string):
  OUT_OF_SCOPE:        planner_node -> out_of_scope_node
  POLICY:               planner_node -> policy_answer_node -> respond_node
  DATA:                 planner_node -> procurement_data_node -> respond_node
  BOTH:                 planner_node -> policy_answer_node -> procurement_data_node -> respond_node

A planner LLM/infrastructure failure also routes to out_of_scope_node
(tools_to_call == [], same as a genuine out-of-scope decision) but carries
a distinct `planner_failed` flag through state and the steps[] trace, and
out_of_scope_node returns a different, honest message in that case -- see
PLANNER_FAILURE_MESSAGE below.
"""

import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from . import planner, qa, tools
from .state import GraphState
from .store import get_chat_model

OUT_OF_SCOPE_MESSAGE = (
    "That looks outside procurement policy, procurement systems, or spend/PO data. "
    "I can help with things like contract/PO thresholds, Ariba how-tos, UNSPSC "
    "classification, or spend and invoice analysis -- try rephrasing around one of those."
)

PLANNER_FAILURE_MESSAGE = (
    "I wasn't able to process this question due to an internal error. Please try again, "
    "or escalate to the L2 procurement team if this persists."
)

SYNTHESIZE_SYSTEM_PROMPT = """Combine the policy answer and the data answer below into one \
concise, coherent response to the user's original question. Preserve citation markers like \
[1] from the policy answer. Do not add any information beyond what's given."""

_synthesize_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYNTHESIZE_SYSTEM_PROMPT),
        ("human", "Original question: {query}\n\nPolicy answer:\n{rag_answer}\n\nData answer:\n{data_answer}"),
    ]
)


def _timed(label: str, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    return result, {"step": label, "latency_ms": elapsed_ms}


def synthesize(query: str, rag_answer: str, data_answer: str) -> str:
    chain = _synthesize_prompt | get_chat_model() | StrOutputParser()
    result = chain.invoke({"query": query, "rag_answer": rag_answer, "data_answer": data_answer})
    # StrOutputParser can return a str-subclass (e.g. langchain_core's TextAccessor) rather
    # than a plain str; synthesize() isn't wrapped by a Pydantic contract like rag_agent/
    # data_agent are, so normalize explicitly here to guarantee a genuine str, matching the
    # original raw-client call's `resp.choices[0].message.content` return type exactly.
    return str(result)


def planner_node(state: GraphState) -> dict:
    plan_result, step = _timed("planner", planner.plan, state["query"])
    step["detail"] = {"tools_to_call": plan_result["tools_to_call"], "reasoning": plan_result["reasoning"]}
    if plan_result["planner_failed"]:
        step["error"] = plan_result["planner_error"]
    return {
        "category": plan_result["category"],
        "tools_to_call": plan_result["tools_to_call"],
        "planner_failed": plan_result["planner_failed"],
        "planner_error": plan_result["planner_error"],
        "steps": [step],
    }


def policy_answer_node(state: GraphState) -> dict:
    rag_result, step1 = _timed("policy_answer", tools.policy_answer, state["query"])
    rag_qa, step2 = _timed(
        "qa_groundedness_check_policy",
        qa.check_rag_groundedness,
        rag_result["answer"],
        rag_result["chunks_used"],
    )
    return {
        "rag_result": rag_result,
        "rag_qa": rag_qa,
        "retrieved_sources": [c["source"] for c in rag_result["citations"]],
        "groundedness": [{"path": "policy", **rag_qa}],
        "steps": [step1, step2],
    }


def procurement_data_node(state: GraphState) -> dict:
    data_result, step1 = _timed(
        "procurement_data_answer", tools.procurement_data_answer, state["query"]
    )
    data_qa, step2 = _timed("qa_groundedness_check_data", qa.check_sql_groundedness, data_result)
    return {
        "data_result": data_result,
        "data_qa": data_qa,
        "sql": data_result.get("sql"),
        "sql_columns": data_result.get("columns", []),
        "sql_rows": data_result.get("rows", []),
        "groundedness": [{"path": "data", **data_qa}],
        "steps": [step1, step2],
    }


def out_of_scope_node(state: GraphState) -> dict:
    if state.get("planner_failed"):
        return {"answer": PLANNER_FAILURE_MESSAGE}
    return {"answer": OUT_OF_SCOPE_MESSAGE}


def respond_node(state: GraphState) -> dict:
    category = state["category"]
    rag_result = state.get("rag_result")
    rag_qa = state.get("rag_qa")
    data_result = state.get("data_result")
    data_qa = state.get("data_qa")

    update: dict = {}

    if rag_result is not None and not (rag_qa is not None and rag_qa["passed"]):
        update["unverified_citations"] = rag_result["citations"]

    rag_ok = rag_qa is not None and rag_qa["passed"]
    data_ok = data_qa is not None and data_qa["passed"]

    if category == "POLICY":
        update["answer"] = rag_result["answer"] if rag_ok else qa.FALLBACK_MESSAGE
        update["citations"] = rag_result["citations"] if rag_ok else []
    elif category == "DATA":
        update["answer"] = data_result["answer"] if data_ok else qa.FALLBACK_MESSAGE
    elif category == "BOTH":
        if rag_ok and data_ok:
            synth, step = _timed(
                "synthesize", synthesize, state["query"], rag_result["answer"], data_result["answer"]
            )
            update["answer"] = synth
            update["citations"] = rag_result["citations"]
            update["steps"] = [step]
        elif rag_ok and not data_ok:
            update["answer"] = (
                rag_result["answer"]
                + "\n\n(Note: I couldn't reliably pull the related spend/PO data for this -- "
                "please verify separately or escalate to L2.)"
            )
            update["citations"] = rag_result["citations"]
        elif data_ok and not rag_ok:
            update["answer"] = (
                data_result["answer"]
                + "\n\n(Note: I couldn't reliably confirm the related policy for this -- "
                "please verify separately or escalate to L2.)"
            )
        else:
            update["answer"] = qa.FALLBACK_MESSAGE

    return update


def _route_after_planner(state: GraphState) -> str:
    # tools_to_call is already canonicalized (deduped, fixed order) by planner.plan() --
    # this function only tests membership, it never relies on list order.
    tools_to_call = state["tools_to_call"]
    if "policy_answer" in tools_to_call:
        return "policy_answer_node"
    if "procurement_data_answer" in tools_to_call:
        return "procurement_data_node"
    return "out_of_scope_node"


def _route_after_policy_answer(state: GraphState) -> str:
    if "procurement_data_answer" in state["tools_to_call"]:
        return "procurement_data_node"
    return "respond_node"


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("planner_node", planner_node)
    builder.add_node("policy_answer_node", policy_answer_node)
    builder.add_node("procurement_data_node", procurement_data_node)
    builder.add_node("respond_node", respond_node)
    builder.add_node("out_of_scope_node", out_of_scope_node)

    builder.set_entry_point("planner_node")
    builder.add_conditional_edges(
        "planner_node",
        _route_after_planner,
        {
            "policy_answer_node": "policy_answer_node",
            "procurement_data_node": "procurement_data_node",
            "out_of_scope_node": "out_of_scope_node",
        },
    )
    builder.add_conditional_edges(
        "policy_answer_node",
        _route_after_policy_answer,
        {"procurement_data_node": "procurement_data_node", "respond_node": "respond_node"},
    )
    builder.add_edge("procurement_data_node", "respond_node")
    builder.add_edge("respond_node", END)
    builder.add_edge("out_of_scope_node", END)

    return builder.compile()


GRAPH = build_graph()
