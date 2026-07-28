"""LangGraph shared state schema -- Step 1.

Mirrors the response dict `orchestrator.handle_query()` has always returned.
This is a sequential migration of the existing router -> rag/data -> qa ->
synthesize control flow onto a LangGraph StateGraph, not a redesign: every
field here corresponds 1:1 to a key in today's response contract.

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
