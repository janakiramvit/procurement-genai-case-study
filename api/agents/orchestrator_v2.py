"""Orchestrator entrypoint -- Step 3B (V2).

Kept separate from orchestrator.py (V1) -- see graph_v2.py's module docstring
for the full isolation rationale. handle_query_v2() accepts conversation
history in addition to the query; memory.validate_and_truncate_history()
independently re-validates/re-truncates it server-side regardless of what the
client sent, before it ever reaches the graph.

Response contract: every V1 field (query, category, steps, answer, citations,
retrieved_sources, unverified_citations, sql*, groundedness, total_latency_ms)
plus new V2-only fields (agent_status, termination_reason,
planner_decision_count, tool_call_count, agent_trace). V1's contract is
unaffected by this file's existence.
"""

import time

from . import memory
from .graph_v2 import AGENT_GRAPH
from .trace import build_trace

# Defensive secondary safety net -- planner_node's own budget checks (§ graph_v2.py) are
# the primary termination guarantee and fire well before this. Worst case under the
# configured budgets is ~13 node visits per turn; 30 leaves generous headroom without
# masking a real bug in the counting logic with a runaway loop.
RECURSION_LIMIT = 30


def handle_query_v2(query: str, conversation_history=None) -> dict:
    t0 = time.perf_counter()

    validated_history = memory.validate_and_truncate_history(conversation_history or [])

    initial_state = {
        "query": query,
        "conversation_history": validated_history,
        "category": None,
        "current_action": None,
        "actions_taken": [],
        "observations": [],
        "called_tools": [],
        "planner_decision_count": 0,
        "tool_call_count": 0,
        "agent_status": "in_progress",
        "termination_reason": None,
        "planner_failed": False,
        "planner_error": None,
        "rag_result": None,
        "rag_qa": None,
        "data_result": None,
        "data_qa": None,
        "answer": None,
        "citations": [],
        "retrieved_sources": [],
        "unverified_citations": [],
        "sql": None,
        "sql_columns": [],
        "sql_rows": [],
        "groundedness": [],
        "steps": [],
    }

    final_state = AGENT_GRAPH.invoke(initial_state, config={"recursion_limit": RECURSION_LIMIT})

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
        "agent_status": final_state.get("agent_status"),
        "termination_reason": final_state.get("termination_reason"),
        "planner_decision_count": final_state.get("planner_decision_count", 0),
        "tool_call_count": final_state.get("tool_call_count", 0),
        "agent_trace": [e.model_dump() for e in build_trace(final_state)],
    }
    response["total_latency_ms"] = round((time.perf_counter() - t0) * 1000)
    return response
