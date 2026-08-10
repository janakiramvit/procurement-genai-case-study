"""Shared Pydantic contracts -- Step 2.

These are internal typed representations, not exposed at function
boundaries: router.route(), rag_agent.answer_from_docs(),
data_agent.answer_from_data(), qa.check_rag_groundedness(), and
qa.check_sql_groundedness() all still return plain dicts with the exact
same keys as before. Each function constructs and validates one of these
models internally, then returns `.model_dump()` at its existing return
boundary -- callers (graph.py's nodes, orchestrator.py, scripts/evaluate.py)
need no changes.

RAGResult/DataResult are intentionally permissive compatibility contracts:
nested fields (citations, chunks_used, columns, rows) stay as plain
list[dict]/list[str] rather than their own nested Pydantic models. A nested
model here risks silently reordering keys, dropping unrecognized fields, or
coercing types during model_dump() -- exactly the kind of behavior drift
this step is meant to avoid. Top-level shape gets real validation; nested
payloads pass through opaque.

QAResult.score is Optional and dumped with exclude_none=True by both QA
functions specifically so the deterministic (SQL) path's groundedness dict
has no "score" key at all -- matching today's dict, which never had one.
DataResult has no such special-casing: today's dict always includes every
key (e.g. "error": None, "answer": None) even on the failure paths, so
DataResult is dumped with plain model_dump(), no exclude_none.
"""

from typing import Literal, Optional

from pydantic import BaseModel


class RouterDecision(BaseModel):
    """Kept only because router.py (deprecated -- superseded by planner.py in
    Step 3A, retained temporarily as comparison code) still references it."""

    category: Literal["POLICY", "DATA", "BOTH", "OUT_OF_SCOPE"]
    reasoning: str


class PlannerDecision(BaseModel):
    """Structured output for planner.py -- Step 3A. The planner selects which
    capabilities a request needs; it does NOT decide execution order (that's
    fixed in code, see planner.canonicalize_tools). tools_to_call is treated
    as an unordered set of requested capabilities regardless of the order the
    model lists them in."""

    tools_to_call: list[Literal["policy_answer", "procurement_data_answer"]]
    reasoning: str


class PolicyAnswerInput(BaseModel):
    query: str


class ProcurementDataInput(BaseModel):
    query: str


class PlannerAction(BaseModel):
    """Structured output for planner.plan_next_action() -- Step 3B.

    `reasoning` is a deliberate, bounded exception to this file's general
    permissive-schema discipline: it's the model's own brief, one-turn
    explanation for the action it chose, surfaced in the execution trace for
    demo/interpretability purposes. It is NOT a mechanistic readout of the
    model's internal computation -- it's a stated rationale generated
    alongside the decision, not a verified cause of it. It is never fed back
    into a later decision's prompt context (see planner._render_actions_taken,
    which intentionally omits it) and never contains raw prompt text.

    Cross-field consistency (CALL_TOOL requires tool+input; FINISH ignores
    both) is validated in code after parsing, not trusted to the schema alone
    -- same discipline as every other structured-output contract here."""

    action: Literal["CALL_TOOL", "FINISH"]
    tool: Optional[Literal["policy_answer", "procurement_data_answer"]] = None
    input: Optional[str] = None
    reasoning: Optional[str] = None


class ConversationTurn(BaseModel):
    """One user+assistant pair -- the explicit wire format for conversation
    memory (Step 3B), sent as already-paired turns rather than a flat message
    list so the server never has to guess how to pair messages up."""

    user: str
    assistant: str


class RAGResult(BaseModel):
    answer: str
    citations: list[dict]
    chunks_used: list[dict]


class DataResult(BaseModel):
    sql: Optional[str] = None
    error: Optional[str] = None
    answer: Optional[str] = None
    columns: list[str] = []
    rows: list[dict] = []


class QAResult(BaseModel):
    passed: bool
    score: Optional[int] = None
    reasoning: str
    method: Literal["llm_judge", "deterministic"]


class SQLGeneration(BaseModel):
    """Internal structured-output schema for data_agent.generate_sql() --
    not one of the four reusable contracts above, just the LLM-facing JSON
    shape data_agent.py's SQL_SYSTEM_PROMPT already asks for."""

    sql: str


class GroundednessJudgment(BaseModel):
    """Internal structured-output schema for qa.check_rag_groundedness() --
    mirrors the LLM judge's existing JSON contract (grounded/score/reasoning)
    exactly, so the LLM-facing prompt/schema doesn't change. The function
    still remaps grounded->passed and adds `method` into QAResult, same as
    today."""

    grounded: bool
    score: int
    reasoning: str
