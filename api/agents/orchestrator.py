"""Orchestrator: deterministic router graph (not a free-running agent loop).

router -> {rag_agent, data_agent} (as needed) -> qa gate -> synthesizer (only if both
paths ran). Deterministic and explicit rather than an autonomous agent loop, by design:
for a scoped L1 helpdesk this is cheaper, faster, and far easier to reason about /
debug / demo than giving a model free rein to decide its own tool sequence.
"""

import time

from . import data_agent, qa, rag_agent, router
from .store import CHAT_MODEL, get_client

OUT_OF_SCOPE_MESSAGE = (
    "That looks outside procurement policy, procurement systems, or spend/PO data. "
    "I can help with things like contract/PO thresholds, Ariba how-tos, UNSPSC "
    "classification, or spend and invoice analysis -- try rephrasing around one of those."
)

SYNTHESIZE_SYSTEM_PROMPT = """Combine the policy answer and the data answer below into one \
concise, coherent response to the user's original question. Preserve citation markers like \
[1] from the policy answer. Do not add any information beyond what's given."""


def _timed(label, steps, fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = round((time.perf_counter() - start) * 1000)
    steps.append({"step": label, "latency_ms": elapsed_ms})
    return result, elapsed_ms


def synthesize(query: str, rag_answer: str, data_answer: str) -> str:
    resp = get_client().chat.completions.create(
        model=CHAT_MODEL,
        temperature=0,
        messages=[
            {"role": "system", "content": SYNTHESIZE_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Original question: {query}\n\nPolicy answer:\n{rag_answer}\n\n"
                    f"Data answer:\n{data_answer}"
                ),
            },
        ],
    )
    return resp.choices[0].message.content


def handle_query(query: str) -> dict:
    t0 = time.perf_counter()
    steps = []

    route_result, _ = _timed("router", steps, router.route, query)
    category = route_result["category"]
    steps[-1]["detail"] = route_result

    response = {
        "query": query,
        "category": category,
        "steps": steps,
        "answer": None,
        "citations": [],
        "retrieved_sources": [],  # what the retriever found, independent of the QA gate --
        # `citations` is user-facing and only populated for QA-passed answers; this field
        # lets eval measure retrieval quality on its own, decoupled from downstream QA/gen.
        "sql": None,
        "sql_columns": [],
        "sql_rows": [],
        "groundedness": [],
    }

    if category == "OUT_OF_SCOPE":
        response["answer"] = OUT_OF_SCOPE_MESSAGE
        response["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
        return response

    rag_result = None
    rag_qa = None
    if category in ("POLICY", "BOTH"):
        rag_result, _ = _timed("rag_retrieve_and_answer", steps, rag_agent.answer_from_docs, query)
        rag_qa, _ = _timed(
            "qa_groundedness_check_policy", steps, qa.check_rag_groundedness, rag_result["answer"], rag_result["chunks_used"]
        )
        response["groundedness"].append({"path": "policy", **rag_qa})
        response["retrieved_sources"] = [c["source"] for c in rag_result["citations"]]

    data_result = None
    data_qa = None
    if category in ("DATA", "BOTH"):
        data_result, _ = _timed("sql_generate_execute_and_answer", steps, data_agent.answer_from_data, query)
        data_qa, _ = _timed("qa_groundedness_check_data", steps, qa.check_sql_groundedness, data_result)
        response["groundedness"].append({"path": "data", **data_qa})
        response["sql"] = data_result.get("sql")
        response["sql_columns"] = data_result.get("columns", [])
        response["sql_rows"] = data_result.get("rows", [])

    rag_ok = rag_qa is not None and rag_qa["passed"]
    data_ok = data_qa is not None and data_qa["passed"]

    if category == "POLICY":
        response["answer"] = rag_result["answer"] if rag_ok else qa.FALLBACK_MESSAGE
        response["citations"] = rag_result["citations"] if rag_ok else []
    elif category == "DATA":
        response["answer"] = data_result["answer"] if data_ok else qa.FALLBACK_MESSAGE
    elif category == "BOTH":
        if rag_ok and data_ok:
            synth, _ = _timed(
                "synthesize", steps, synthesize, query, rag_result["answer"], data_result["answer"]
            )
            response["answer"] = synth
            response["citations"] = rag_result["citations"]
        elif rag_ok and not data_ok:
            response["answer"] = rag_result["answer"] + "\n\n(Note: I couldn't reliably pull the related spend/PO data for this -- please verify separately or escalate to L2.)"
            response["citations"] = rag_result["citations"]
        elif data_ok and not rag_ok:
            response["answer"] = data_result["answer"] + "\n\n(Note: I couldn't reliably confirm the related policy for this -- please verify separately or escalate to L2.)"
        else:
            response["answer"] = qa.FALLBACK_MESSAGE

    response["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return response
