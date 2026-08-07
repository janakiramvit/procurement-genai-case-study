"""LangGraph shared state schema -- Step 3B agent loop.

Kept entirely separate from state.py (Step 1/3A's GraphState) so V1's schema
is never touched by V2's evolution -- see graph_v2.py's module docstring for
the full rationale.

Additive relative to GraphState: `rag_result`/`rag_qa`/`data_result`/`data_qa`/
`answer`/`citations`/etc. are the exact same field names Step 1's respond_node
already reads, reused unchanged (imported directly from graph.py) so the loop
only has to own dispatch, not response synthesis.

`called_tools` is the single source of truth for "what's actually been
executed this turn" -- both duplicate-detection and per-tool execution counts
are derived from it by scanning (it's bounded to at most
MAX_TOOL_EXECUTIONS=6 entries, so this is cheap), rather than maintaining a
second, redundant per-tool counter that could drift out of sync.

`conversation_history` is the one field that crosses turn boundaries -- it's
read-only input to this turn (already validated/truncated by memory.py before
the graph is invoked), never written by any node.
"""

import operator
from typing import Annotated, Optional, TypedDict


class AgentGraphState(TypedDict, total=False):
    query: str
    conversation_history: list  # list[{"user": str, "assistant": str}], server-validated

    category: Optional[str]

    current_action: Optional[dict]  # last PlannerAction as a dict, set by planner_node
    actions_taken: Annotated[list, operator.add]  # [{decision_number, action, tool, input, status}]
    observations: Annotated[list, operator.add]  # [{tool, status, answer_summary, qa_passed, qa_method}]
    called_tools: Annotated[list, operator.add]  # [{"tool": str, "normalized_input": str}] -- real executions only

    planner_decision_count: Annotated[int, operator.add]
    tool_call_count: Annotated[int, operator.add]

    agent_status: Optional[str]  # in_progress | finished | budget_exhausted | planner_failed | tool_failed
    termination_reason: Optional[str]
    planner_failed: bool
    planner_error: Optional[str]

    rag_result: Optional[dict]
    rag_qa: Optional[dict]
    data_result: Optional[dict]
    data_qa: Optional[dict]

    answer: Optional[str]
    citations: list
    retrieved_sources: list
    unverified_citations: list

    sql: Optional[str]
    sql_columns: list
    sql_rows: list

    groundedness: Annotated[list, operator.add]
    steps: Annotated[list, operator.add]
