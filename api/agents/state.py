"""LangGraph shared state schema -- Step 1, extended in Step 3A.

Mirrors the response dict `orchestrator.handle_query()` has always returned.
This is a sequential migration of the existing router -> rag/data -> qa ->
synthesize control flow onto a LangGraph StateGraph, not a redesign: every
field here corresponds 1:1 to a key in today's response contract.

tools_to_call/planner_failed/planner_error are additive Step 3A fields --
they're internal (not part of the existing API response contract) and are
populated by planner_node so a genuine OUT_OF_SCOPE decision (tools_to_call
== [], planner_failed == False) is never indistinguishable, in state or
trace, from a planner LLM/infrastructure failure that degraded to the same
empty tool list (tools_to_call == [], planner_failed == True).

`groundedness` and `steps` use an append reducer (operator.add) because each
node that runs contributes its own increment to those lists rather than
rewriting the whole list -- the idiomatic LangGraph pattern for partial
state updates. Harmless under Step 1's purely sequential execution, and
forward-compatible with the later step where multiple branches may
contribute to these fields concurrently.

All other fields have exactly one writer node per request path, so they
need no reducer -- a later node's partial update simply leaves an untouched
key at whatever the initial state (or an earlier node) set it to.
"""

import operator
from typing import Annotated, Optional, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    category: Optional[str]

    tools_to_call: list
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
