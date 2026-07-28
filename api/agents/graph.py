"""LangGraph parent graph -- Step 1.

Reproduces the existing router -> rag/data -> qa -> synthesize control flow
(previously hand-written in orchestrator.py) on a LangGraph StateGraph, node
for node, edge for edge, same order. No parallelism, no sub-agents, no
tools, no LangChain wrappers: every node below is a thin wrapper calling the
existing router / rag_agent / data_agent / qa functions unchanged.

Node execution order per category (identical to the current pipeline):
  OUT_OF_SCOPE: router_node -> out_of_scope_node
  POLICY:       router_node -> rag_node -> respond_node
  DATA:         router_node -> data_node -> respond_node
  BOTH:         router_node -> rag_node -> data_node -> respond_node
"""

import time

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph

from . import data_agent, qa, rag_agent, router
from .state import GraphState
from .store import get_chat_model

OUT_OF_SCOPE_MESSAGE = (
    "That looks outside procurement policy, procurement systems, or spend/PO data. "
    "I can help with things like contract/PO thresholds, Ariba how-tos, UNSPSC "
    "classification, or spend and invoice analysis -- try rephrasing around one of those."
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


def router_node(state: GraphState) -> dict:
    route_result, step = _timed("router", router.route, state["query"])
    step["detail"] = route_result
    return {"category": route_result["category"], "steps": [step]}


def rag_node(state: GraphState) -> dict:
    rag_result, step1 = _timed("rag_retrieve_and_answer", rag_agent.answer_from_docs, state["query"])
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


def data_node(state: GraphState) -> dict:
    data_result, step1 = _timed(
        "sql_generate_execute_and_answer", data_agent.answer_from_data, state["query"]
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


def _route_after_router(state: GraphState) -> str:
    return state["category"]


def _route_after_rag(state: GraphState) -> str:
    return state["category"]


def build_graph():
    builder = StateGraph(GraphState)
    builder.add_node("router_node", router_node)
    builder.add_node("rag_node", rag_node)
    builder.add_node("data_node", data_node)
    builder.add_node("respond_node", respond_node)
    builder.add_node("out_of_scope_node", out_of_scope_node)

    builder.set_entry_point("router_node")
    builder.add_conditional_edges(
        "router_node",
        _route_after_router,
        {"POLICY": "rag_node", "BOTH": "rag_node", "DATA": "data_node", "OUT_OF_SCOPE": "out_of_scope_node"},
    )
    builder.add_conditional_edges(
        "rag_node",
        _route_after_rag,
        {"BOTH": "data_node", "POLICY": "respond_node"},
    )
    builder.add_edge("data_node", "respond_node")
    builder.add_edge("respond_node", END)
    builder.add_edge("out_of_scope_node", END)

    return builder.compile()


GRAPH = build_graph()
