"""LangGraph parent graph -- Step 3B bounded agent loop.

Kept entirely SEPARATE from graph.py (Step 1/3A's graph): V1's graph.py,
state.py, and orchestrator.py are never imported here except for the pieces
that are genuinely identical and safe to reuse as-is -- respond_node,
synthesize, and the two terminal messages -- so future changes to V2's loop
can never risk V1's behavior, and vice versa.

Topology:
  START -> planner_node
  planner_node -(route_after_planner)-> {tool_execution_node, respond_node, terminal_no_answer_node}
  tool_execution_node -(route_after_tool_execution)-> {planner_node, terminal_no_answer_node}
  respond_node -> END
  terminal_no_answer_node -> END

Budgets (global per user turn, not per-tool for the two ceilings below):
  MAX_PLANNER_DECISIONS = 7   -- up to 6 tool calls + 1 FINISH
  MAX_TOOL_EXECUTIONS   = 6   -- across both capabilities combined
  MAX_EXECUTIONS_PER_TOOL = 3 -- ceiling on any single capability

All three are enforced in planner_node BEFORE spending an LLM call (once a
ceiling is hit, FINISH is synthesized in code, no wasted call) or in
tool_execution_node before re-executing a tool (duplicate / per-tool-limit
requests are blocked without being re-run, recorded, and looped back to the
planner so it can pick something else or FINISH -- this costs a planner
decision, not a tool execution).
"""

from . import planner
from . import qa as qa_module
from . import tools
from .contracts import PlannerAction
from .graph import PLANNER_FAILURE_MESSAGE, _timed, respond_node
from .state_v2 import AgentGraphState
from langgraph.graph import END, StateGraph

MAX_PLANNER_DECISIONS = 7
MAX_TOOL_EXECUTIONS = 6
MAX_EXECUTIONS_PER_TOOL = 3

OUT_OF_SCOPE_MESSAGE = (
    "That looks outside procurement policy, procurement systems, or spend/PO data. "
    "I can help with things like contract/PO thresholds, Ariba how-tos, UNSPSC "
    "classification, or spend and invoice analysis -- try rephrasing around one of those."
)

TOOL_FAILURE_MESSAGE = (
    "I wasn't able to gather the information needed for this due to an internal error "
    "part-way through. Please try again, or escalate to the L2 procurement team if this persists."
)

BUDGET_EXHAUSTED_NO_EVIDENCE_MESSAGE = (
    "I wasn't able to gather any grounded evidence for this within my execution budget. "
    "Please try rephrasing, or escalate to the L2 procurement team."
)

def _normalize_input(text) -> str:
    return " ".join((text or "").strip().lower().split())


def planner_node(state: AgentGraphState) -> dict:
    decision_count = state.get("planner_decision_count", 0)
    tool_count = state.get("tool_call_count", 0)
    next_decision_number = decision_count + 1

    remaining_decisions = MAX_PLANNER_DECISIONS - decision_count
    remaining_tool_calls = MAX_TOOL_EXECUTIONS - tool_count

    if remaining_decisions <= 0 or remaining_tool_calls <= 0:
        reason = (
            f"max planner decisions ({MAX_PLANNER_DECISIONS}) reached"
            if remaining_decisions <= 0
            else f"max tool executions ({MAX_TOOL_EXECUTIONS}) reached"
        )
        called = [c["tool"] for c in state.get("called_tools", [])]
        category = planner.derive_category(planner.canonicalize_tools(called))
        return {
            "current_action": {"action": "FINISH", "tool": None, "input": None},
            "actions_taken": [
                {"decision_number": next_decision_number, "action": "FINISH", "tool": None, "input": None, "status": "forced"}
            ],
            "planner_decision_count": 1,
            "agent_status": "budget_exhausted",
            "termination_reason": reason,
            "category": category,
            "steps": [{"step": "planner", "latency_ms": 0, "detail": {"decision": next_decision_number, "forced": True}}],
        }

    plan_result, step = _timed(
        "planner",
        planner.plan_next_action,
        state["query"],
        state.get("conversation_history", []),
        state.get("actions_taken", []),
        state.get("observations", []),
        remaining_decisions,
        remaining_tool_calls,
    )
    step["detail"] = {"decision": next_decision_number}

    action: PlannerAction = plan_result["action"]
    update: dict = {
        "current_action": action.model_dump(),
        "planner_decision_count": 1,
        "steps": [step],
    }

    if plan_result["planner_failed"]:
        step["error"] = plan_result["planner_error"]
        update["planner_failed"] = True
        update["planner_error"] = plan_result["planner_error"]
        update["agent_status"] = "planner_failed"
        update["termination_reason"] = "planner call failed"
        update["actions_taken"] = [
            {"decision_number": next_decision_number, "action": "FINISH", "tool": None, "input": None, "status": "failed"}
        ]
        return update

    if action.action == "FINISH":
        called = [c["tool"] for c in state.get("called_tools", [])]
        update["agent_status"] = "finished"
        update["termination_reason"] = "planner determined sufficient evidence"
        update["category"] = planner.derive_category(planner.canonicalize_tools(called))
        update["actions_taken"] = [
            {
                "decision_number": next_decision_number,
                "action": "FINISH",
                "tool": None,
                "input": None,
                "status": "genuine",
                "reasoning": action.reasoning,
            }
        ]
        return update

    # CALL_TOOL -- duplicate/per-tool-limit checks happen in tool_execution_node, which
    # is the node that knows whether this specific (tool, input) is actually blocked.
    update["agent_status"] = "in_progress"
    return update


def tool_execution_node(state: AgentGraphState) -> dict:
    action = state["current_action"]
    tool_name = action["tool"]
    raw_input = action["input"]
    reasoning = action.get("reasoning")
    decision_number = state.get("planner_decision_count", 0)

    normalized = _normalize_input(raw_input)
    called_tools = state.get("called_tools", [])
    per_tool_count = sum(1 for c in called_tools if c["tool"] == tool_name)
    is_duplicate = any(c["tool"] == tool_name and c["normalized_input"] == normalized for c in called_tools)

    if is_duplicate:
        return {
            "actions_taken": [
                {"decision_number": decision_number, "action": "CALL_TOOL", "tool": tool_name, "input": raw_input, "status": "blocked_duplicate", "reasoning": reasoning}
            ],
            "observations": [
                {
                    "decision_number": decision_number,
                    "tool": tool_name,
                    "status": "blocked",
                    "answer_summary": "Blocked: identical call already made this turn.",
                    "qa_passed": None,
                    "qa_method": None,
                }
            ],
        }

    if per_tool_count >= MAX_EXECUTIONS_PER_TOOL:
        return {
            "actions_taken": [
                {"decision_number": decision_number, "action": "CALL_TOOL", "tool": tool_name, "input": raw_input, "status": "blocked_per_tool_limit", "reasoning": reasoning}
            ],
            "observations": [
                {
                    "decision_number": decision_number,
                    "tool": tool_name,
                    "status": "blocked",
                    "answer_summary": f"Blocked: {tool_name} has already run {per_tool_count} times this turn (limit {MAX_EXECUTIONS_PER_TOOL}).",
                    "qa_passed": None,
                    "qa_method": None,
                }
            ],
        }

    try:
        if tool_name == "policy_answer":
            result, step1 = _timed("policy_answer", tools.policy_answer, raw_input)
            qa, step2 = _timed(
                "qa_groundedness_check_policy", qa_module.check_rag_groundedness, result["answer"], result["chunks_used"]
            )
            capability_update = {
                "rag_result": result,
                "rag_qa": qa,
                "retrieved_sources": [c["source"] for c in result["citations"]],
                "groundedness": [{"path": "policy", **qa}],
            }
            answer_text = result["answer"]
        else:
            result, step1 = _timed("procurement_data_answer", tools.procurement_data_answer, raw_input)
            qa, step2 = _timed("qa_groundedness_check_data", qa_module.check_sql_groundedness, result)
            capability_update = {
                "data_result": result,
                "data_qa": qa,
                "sql": result.get("sql"),
                "sql_columns": result.get("columns", []),
                "sql_rows": result.get("rows", []),
                "groundedness": [{"path": "data", **qa}],
            }
            answer_text = result.get("answer") or result.get("error") or ""
    except Exception as e:
        return {
            "actions_taken": [
                {"decision_number": decision_number, "action": "CALL_TOOL", "tool": tool_name, "input": raw_input, "status": "executed", "reasoning": reasoning}
            ],
            "observations": [
                {
                    "decision_number": decision_number,
                    "tool": tool_name,
                    "status": "failed",
                    "answer_summary": f"Tool execution failed: {e}",
                    "qa_passed": None,
                    "qa_method": None,
                }
            ],
            "called_tools": [{"tool": tool_name, "normalized_input": normalized}],
            "tool_call_count": 1,
            "agent_status": "tool_failed",
            "termination_reason": f"{tool_name} raised an exception",
            "steps": [{"step": tool_name, "latency_ms": 0, "error": str(e)}],
        }

    return {
        **capability_update,
        "actions_taken": [
            {"decision_number": decision_number, "action": "CALL_TOOL", "tool": tool_name, "input": raw_input, "status": "executed", "reasoning": reasoning}
        ],
        "observations": [
            {
                "decision_number": decision_number,
                "tool": tool_name,
                "status": "completed",
                "answer_summary": answer_text,
                "qa_passed": qa["passed"],
                "qa_method": qa["method"],
            }
        ],
        "called_tools": [{"tool": tool_name, "normalized_input": normalized}],
        "tool_call_count": 1,
        "steps": [step1, step2],
    }


def terminal_no_answer_node(state: AgentGraphState) -> dict:
    status = state.get("agent_status")
    if status == "planner_failed":
        return {"answer": PLANNER_FAILURE_MESSAGE}
    if status == "tool_failed":
        return {"answer": TOOL_FAILURE_MESSAGE}
    if status == "budget_exhausted":
        return {"answer": BUDGET_EXHAUSTED_NO_EVIDENCE_MESSAGE}
    return {"answer": OUT_OF_SCOPE_MESSAGE}


def route_after_planner(state: AgentGraphState) -> str:
    status = state.get("agent_status")
    if status in ("planner_failed", "tool_failed"):
        return "terminal_no_answer_node"

    action = state.get("current_action") or {}
    if action.get("action") == "CALL_TOOL":
        return "tool_execution_node"

    # FINISH -- genuine or budget-forced
    if status == "budget_exhausted" and not state.get("called_tools"):
        return "terminal_no_answer_node"
    if state.get("category") == "OUT_OF_SCOPE":
        return "terminal_no_answer_node"
    return "respond_node"


def route_after_tool_execution(state: AgentGraphState) -> str:
    if state.get("agent_status") == "tool_failed":
        return "terminal_no_answer_node"
    return "planner_node"


def build_graph():
    builder = StateGraph(AgentGraphState)
    builder.add_node("planner_node", planner_node)
    builder.add_node("tool_execution_node", tool_execution_node)
    builder.add_node("respond_node", respond_node)  # reused unchanged from graph.py (Step 1)
    builder.add_node("terminal_no_answer_node", terminal_no_answer_node)

    builder.set_entry_point("planner_node")
    builder.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "tool_execution_node": "tool_execution_node",
            "respond_node": "respond_node",
            "terminal_no_answer_node": "terminal_no_answer_node",
        },
    )
    builder.add_conditional_edges(
        "tool_execution_node",
        route_after_tool_execution,
        {"planner_node": "planner_node", "terminal_no_answer_node": "terminal_no_answer_node"},
    )
    builder.add_edge("respond_node", END)
    builder.add_edge("terminal_no_answer_node", END)

    return builder.compile()


AGENT_GRAPH = build_graph()
