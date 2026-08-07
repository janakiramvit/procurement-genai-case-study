"""Deterministic unit tests for Step 3B's bounded plan-act-observe loop.

No OpenAI API calls: planner.plan_next_action() and the tool/QA functions are
mocked, so these test graph_v2.py's own logic (budget enforcement, duplicate/
per-tool-limit blocking, routing, failure handling) directly -- not the LLM's
judgment. Live smoke tests (separately, with a real API key) cover whether the
prompts actually produce good decisions.

Run directly: python3 tests/test_agent_loop.py
"""

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from agents import graph_v2  # noqa: E402
from agents import planner as planner_module  # noqa: E402
from agents import qa as qa_module  # noqa: E402
from agents import tools as tools_module  # noqa: E402
from agents.contracts import PlannerAction  # noqa: E402

_FAILURES = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def _base_state(**overrides) -> dict:
    state = {
        "query": "test query",
        "conversation_history": [],
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
    state.update(overrides)
    return state


_FAKE_RAG_RESULT = {
    "answer": "Policy answer text.",
    "citations": [{"marker": 1, "source": "doc.pdf", "location": "page 1", "score": 0.9}],
    "chunks_used": [{"source": "doc.pdf", "location": "page 1", "text": "some text", "score": 0.9}],
}
_FAKE_DATA_RESULT = {
    "sql": "SELECT 1",
    "error": None,
    "answer": "Data answer text.",
    "columns": ["x"],
    "rows": [{"x": 1}],
}
_FAKE_QA_PASS = {"passed": True, "score": 5, "reasoning": "ok", "method": "llm_judge"}
_FAKE_QA_DATA_PASS = {"passed": True, "reasoning": "ok", "method": "deterministic"}


# --- planner_node: budget enforcement happens BEFORE spending an LLM call ---


def test_planner_node_forced_finish_at_decision_budget():
    state = _base_state(planner_decision_count=graph_v2.MAX_PLANNER_DECISIONS, tool_call_count=1)
    with patch.object(planner_module, "plan_next_action") as mock_plan:
        result = graph_v2.planner_node(state)
    check("decision budget: plan_next_action NOT called", mock_plan.call_count == 0)
    check("decision budget: agent_status == budget_exhausted", result["agent_status"] == "budget_exhausted")
    check("decision budget: current_action is forced FINISH", result["current_action"]["action"] == "FINISH")
    check(
        "decision budget: termination_reason mentions the limit",
        f"({graph_v2.MAX_PLANNER_DECISIONS})" in result["termination_reason"],
    )


def test_planner_node_forced_finish_at_tool_budget():
    state = _base_state(planner_decision_count=1, tool_call_count=graph_v2.MAX_TOOL_EXECUTIONS)
    with patch.object(planner_module, "plan_next_action") as mock_plan:
        result = graph_v2.planner_node(state)
    check("tool budget: plan_next_action NOT called", mock_plan.call_count == 0)
    check("tool budget: agent_status == budget_exhausted", result["agent_status"] == "budget_exhausted")


def test_planner_node_calls_llm_when_budget_available():
    action = PlannerAction(action="CALL_TOOL", tool="procurement_data_answer", input="total IBM spend")
    with patch.object(
        planner_module, "plan_next_action", return_value={"action": action, "planner_failed": False, "planner_error": None}
    ) as mock_plan:
        result = graph_v2.planner_node(_base_state())
    check("calls LLM when budget available", mock_plan.call_count == 1)
    check("agent_status stays in_progress on CALL_TOOL", result["agent_status"] == "in_progress")
    check("current_action captured correctly", result["current_action"]["tool"] == "procurement_data_answer")


def test_planner_node_genuine_finish_derives_category():
    action = PlannerAction(action="FINISH", tool=None, input=None)
    state = _base_state(called_tools=[{"tool": "policy_answer", "normalized_input": "x"}])
    with patch.object(
        planner_module, "plan_next_action", return_value={"action": action, "planner_failed": False, "planner_error": None}
    ):
        result = graph_v2.planner_node(state)
    check("genuine FINISH: agent_status == finished", result["agent_status"] == "finished")
    check("genuine FINISH: category derived from called_tools", result["category"] == "POLICY")


def test_planner_node_records_planner_failure():
    with patch.object(
        planner_module, "plan_next_action", return_value={"action": PlannerAction(action="FINISH"), "planner_failed": True, "planner_error": "boom"}
    ):
        result = graph_v2.planner_node(_base_state())
    check("planner failure: agent_status == planner_failed", result["agent_status"] == "planner_failed")
    check("planner failure: planner_error recorded", result["planner_error"] == "boom")


# --- tool_execution_node: duplicate/per-tool-limit blocking, execution, failure ---


def test_tool_execution_executes_and_records():
    state = _base_state(current_action={"action": "CALL_TOOL", "tool": "policy_answer", "input": "what approval applies?"})
    with patch.object(tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT), patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ):
        result = graph_v2.tool_execution_node(state)
    check("execute: tool_call_count incremented", result["tool_call_count"] == 1)
    check("execute: called_tools recorded", result["called_tools"][0]["tool"] == "policy_answer")
    check("execute: actions_taken status == executed", result["actions_taken"][0]["status"] == "executed")
    check("execute: rag_result populated", result["rag_result"] == _FAKE_RAG_RESULT)
    check("execute: observation qa_passed True", result["observations"][0]["qa_passed"] is True)


def test_tool_execution_blocks_exact_duplicate():
    state = _base_state(
        current_action={"action": "CALL_TOOL", "tool": "policy_answer", "input": "  What Approval Applies?  "},
        called_tools=[{"tool": "policy_answer", "normalized_input": "what approval applies?"}],
    )
    with patch.object(tools_module, "policy_answer") as mock_tool:
        result = graph_v2.tool_execution_node(state)
    check("duplicate: underlying tool NOT called", mock_tool.call_count == 0)
    check("duplicate: actions_taken status == blocked_duplicate", result["actions_taken"][0]["status"] == "blocked_duplicate")
    check("duplicate: no tool_call_count key (doesn't consume tool budget)", "tool_call_count" not in result)


def test_tool_execution_allows_legitimate_refinement():
    state = _base_state(
        current_action={
            "action": "CALL_TOOL",
            "tool": "policy_answer",
            "input": "what approval policy applies to a $700K IT hardware purchase?",
        },
        called_tools=[{"tool": "policy_answer", "normalized_input": "what approval policy applies to this purchase?"}],
    )
    with patch.object(tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT) as mock_tool, patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ):
        result = graph_v2.tool_execution_node(state)
    check("refinement: underlying tool IS called (not blocked)", mock_tool.call_count == 1)
    check("refinement: tool_call_count incremented", result["tool_call_count"] == 1)
    check("refinement: actions_taken status == executed", result["actions_taken"][0]["status"] == "executed")


def test_tool_execution_blocks_per_tool_limit():
    called = [{"tool": "policy_answer", "normalized_input": f"input {i}"} for i in range(graph_v2.MAX_EXECUTIONS_PER_TOOL)]
    state = _base_state(
        current_action={"action": "CALL_TOOL", "tool": "policy_answer", "input": "a brand new distinct input"},
        called_tools=called,
    )
    with patch.object(tools_module, "policy_answer") as mock_tool:
        result = graph_v2.tool_execution_node(state)
    check("per-tool limit: underlying tool NOT called", mock_tool.call_count == 0)
    check(
        "per-tool limit: actions_taken status == blocked_per_tool_limit",
        result["actions_taken"][0]["status"] == "blocked_per_tool_limit",
    )


def test_tool_execution_handles_policy_tool_failure():
    state = _base_state(current_action={"action": "CALL_TOOL", "tool": "policy_answer", "input": "x"})
    with patch.object(tools_module, "policy_answer", side_effect=RuntimeError("embedding API down")):
        result = graph_v2.tool_execution_node(state)
    check("policy tool failure: agent_status == tool_failed", result["agent_status"] == "tool_failed")
    check("policy tool failure: tool_call_count still incremented (attempted)", result["tool_call_count"] == 1)
    check("policy tool failure: observation status == failed", result["observations"][0]["status"] == "failed")


def test_tool_execution_handles_data_tool_failure():
    state = _base_state(current_action={"action": "CALL_TOOL", "tool": "procurement_data_answer", "input": "x"})
    with patch.object(tools_module, "procurement_data_answer", side_effect=RuntimeError("duckdb connection error")):
        result = graph_v2.tool_execution_node(state)
    check("data tool failure: agent_status == tool_failed", result["agent_status"] == "tool_failed")
    check("data tool failure: observation status == failed", result["observations"][0]["status"] == "failed")


# --- routing ---


def test_route_after_planner():
    check(
        "route: CALL_TOOL -> tool_execution_node",
        graph_v2.route_after_planner(_base_state(current_action={"action": "CALL_TOOL"})) == "tool_execution_node",
    )
    check(
        "route: FINISH + POLICY category -> respond_node",
        graph_v2.route_after_planner(_base_state(current_action={"action": "FINISH"}, category="POLICY")) == "respond_node",
    )
    check(
        "route: FINISH + OUT_OF_SCOPE -> terminal_no_answer_node",
        graph_v2.route_after_planner(_base_state(current_action={"action": "FINISH"}, category="OUT_OF_SCOPE"))
        == "terminal_no_answer_node",
    )
    check(
        "route: planner_failed -> terminal_no_answer_node",
        graph_v2.route_after_planner(_base_state(agent_status="planner_failed")) == "terminal_no_answer_node",
    )
    check(
        "route: budget_exhausted with zero evidence -> terminal_no_answer_node",
        graph_v2.route_after_planner(
            _base_state(agent_status="budget_exhausted", current_action={"action": "FINISH"}, called_tools=[])
        )
        == "terminal_no_answer_node",
    )
    check(
        "route: budget_exhausted WITH evidence -> respond_node",
        graph_v2.route_after_planner(
            _base_state(
                agent_status="budget_exhausted",
                current_action={"action": "FINISH"},
                category="DATA",
                called_tools=[{"tool": "procurement_data_answer", "normalized_input": "x"}],
            )
        )
        == "respond_node",
    )


def test_route_after_tool_execution():
    check(
        "route: tool_failed -> terminal_no_answer_node",
        graph_v2.route_after_tool_execution(_base_state(agent_status="tool_failed")) == "terminal_no_answer_node",
    )
    check(
        "route: otherwise -> planner_node (loop back)",
        graph_v2.route_after_tool_execution(_base_state(agent_status="in_progress")) == "planner_node",
    )


# --- full-graph integration: exercises the actual loop edge, not just node functions ---


def test_full_loop_data_then_policy_sequential():
    scripted = iter(
        [
            {
                "action": PlannerAction(action="CALL_TOOL", tool="procurement_data_answer", input="IBM spend"),
                "planner_failed": False,
                "planner_error": None,
            },
            {
                "action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="approval policy for that spend"),
                "planner_failed": False,
                "planner_error": None,
            },
            {"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None},
        ]
    )
    with patch.object(planner_module, "plan_next_action", side_effect=lambda *a, **kw: next(scripted)), patch.object(
        tools_module, "procurement_data_answer", return_value=_FAKE_DATA_RESULT
    ), patch.object(tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT), patch.object(
        qa_module, "check_sql_groundedness", return_value=_FAKE_QA_DATA_PASS
    ), patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ), patch(
        "agents.graph.synthesize", return_value="Combined grounded answer."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})

    check("sequential: agent_status == finished", final_state["agent_status"] == "finished")
    check("sequential: category == BOTH", final_state["category"] == "BOTH")
    check("sequential: planner_decision_count == 3", final_state["planner_decision_count"] == 3)
    check("sequential: tool_call_count == 2", final_state["tool_call_count"] == 2)
    check("sequential: called_tools order preserved (data first, then policy)", [c["tool"] for c in final_state["called_tools"]] == ["procurement_data_answer", "policy_answer"])
    check("sequential: answer is the synthesized combination", final_state["answer"] == "Combined grounded answer.")


def test_full_loop_forced_termination():
    # A planner that ALWAYS wants to call more tools -- global tool budget must still
    # deterministically terminate the loop without ever exceeding MAX_TOOL_EXECUTIONS,
    # alternating tools to also avoid tripping the exact-duplicate block first.
    def always_call_more(*args, **kwargs):
        # args[3] is `observations`, whose length tells us how many real tool calls
        # have happened so far -- alternate tools based on parity so this never hits
        # the per-tool cap before the global cap does.
        n = len(args[3])
        tool = "policy_answer" if n % 2 == 0 else "procurement_data_answer"
        return {
            "action": PlannerAction(action="CALL_TOOL", tool=tool, input=f"distinct input {n}"),
            "planner_failed": False,
            "planner_error": None,
        }

    with patch.object(planner_module, "plan_next_action", side_effect=always_call_more), patch.object(
        tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT
    ), patch.object(tools_module, "procurement_data_answer", return_value=_FAKE_DATA_RESULT), patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ), patch.object(
        qa_module, "check_sql_groundedness", return_value=_FAKE_QA_DATA_PASS
    ), patch(
        "agents.graph.synthesize", return_value="Combined."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})

    check("forced termination: agent_status == budget_exhausted", final_state["agent_status"] == "budget_exhausted")
    check(
        "forced termination: tool_call_count never exceeds MAX_TOOL_EXECUTIONS",
        final_state["tool_call_count"] <= graph_v2.MAX_TOOL_EXECUTIONS,
    )
    check(
        "forced termination: planner_decision_count never exceeds MAX_PLANNER_DECISIONS",
        final_state["planner_decision_count"] <= graph_v2.MAX_PLANNER_DECISIONS,
    )
    check("forced termination: terminates with SOME evidence collected", len(final_state["called_tools"]) > 0)


def run():
    test_planner_node_forced_finish_at_decision_budget()
    test_planner_node_forced_finish_at_tool_budget()
    test_planner_node_calls_llm_when_budget_available()
    test_planner_node_genuine_finish_derives_category()
    test_planner_node_records_planner_failure()
    test_tool_execution_executes_and_records()
    test_tool_execution_blocks_exact_duplicate()
    test_tool_execution_allows_legitimate_refinement()
    test_tool_execution_blocks_per_tool_limit()
    test_tool_execution_handles_policy_tool_failure()
    test_tool_execution_handles_data_tool_failure()
    test_route_after_planner()
    test_route_after_tool_execution()
    test_full_loop_data_then_policy_sequential()
    test_full_loop_forced_termination()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: {_FAILURES}")
        sys.exit(1)
    print("All deterministic agent-loop tests passed.")


if __name__ == "__main__":
    run()
