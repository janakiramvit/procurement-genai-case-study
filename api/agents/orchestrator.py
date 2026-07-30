"""Orchestrator entrypoint -- Step 1, extended in Step 3A.

`handle_query()` keeps its exact original signature and response contract.
Internally it builds an initial state, invokes the compiled LangGraph parent
graph (api/agents/graph.py) -- planner -> {policy_answer, procurement_data}
(as needed) -> qa gate -> synthesizer -- and maps the final state back into
the same response dict shape callers (api/chat.py, scripts/evaluate.py)
already depend on.
"""

import time

from .graph import GRAPH


def handle_query(query: str) -> dict:
    t0 = time.perf_counter()

    initial_state = {
        "query": query,
        "category": None,
        "tools_to_call": [],
        "planner_failed": False,
        "planner_error": None,
        "rag_result": None,
        "rag_qa": None,
        "data_result": None,
        "data_qa": None,
        "answer": None,
        "citations": [],
        "retrieved_sources": [],  # what the retriever found, independent of the QA gate --
        # `citations` is user-facing and only populated for QA-passed answers; this field
        # lets eval measure retrieval quality on its own, decoupled from downstream QA/gen.
        "unverified_citations": [],  # full citation objects for a policy path that was
        # attempted but failed groundedness -- lets the UI show what was retrieved even
        # when the generated answer from it wasn't trusted, clearly labeled as unverified.
        "sql": None,
        "sql_columns": [],
        "sql_rows": [],
        "groundedness": [],
        "steps": [],
    }

    final_state = GRAPH.invoke(initial_state)

    response = {
        "query": query,
        "category": final_state.get("category"),
        "steps": final_state.get("steps", []),
        "answer": final_state.get("answer"),
        "citations": final_state.get("citations", []),
        "retrieved_sources": final_state.get("retrieved_sources", []),
        "unverified_citations": final_state.get("unverified_citations", []),
        "sql": final_state.get("sql"),
        "sql_columns": final_state.get("sql_columns", []),
        "sql_rows": final_state.get("sql_rows", []),
        "groundedness": final_state.get("groundedness", []),
    }
    response["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return response
