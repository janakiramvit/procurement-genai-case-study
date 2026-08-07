"""Deterministic tests proving Step 3B's semantic-sufficiency FINISH behavior
is safe by construction -- not just "the planner usually behaves," but that
the SYSTEM (deterministic code, reused unchanged from Step 1) cannot be
tricked into producing an ungrounded or miscategorized answer even if the
planner's own judgment about "sufficient evidence" is imperfect.

Documents and verifies:
"V1 selects capabilities upfront. V2 independently evaluates sufficiency
after each observation." -- V1's planner commits to a full capability set
before any tool runs; V2 decides one action at a time, conditioned on real
observations, and can genuinely stop early or continue based on what it's
actually seen.

No OpenAI API calls -- same RunnableLambda/mock approach as
tests/test_agent_loop.py.

Run directly: python3 tests/test_semantic_finish.py
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
from agents.qa import FALLBACK_MESSAGE  # noqa: E402

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
_FAKE_DATA_RESULT = {"sql": "SELECT 1", "error": None, "answer": "Data answer text.", "columns": ["x"], "rows": [{"x": 1}]}
_FAKE_QA_PASS = {"passed": True, "score": 5, "reasoning": "ok", "method": "llm_judge"}
_FAKE_QA_FAIL = {"passed": False, "score": 2, "reasoning": "unsupported", "method": "llm_judge"}
_FAKE_QA_DATA_PASS = {"passed": True, "reasoning": "ok", "method": "deterministic"}


def _run_scripted_loop(scripted_actions, tool_patches: dict):
    """tool_patches maps (module, attr_name) -> return_value."""
    it = iter(scripted_actions)
    patches = [patch.object(planner_module, "plan_next_action", side_effect=lambda *a, **kw: next(it))]
    for (module, attr), value in tool_patches.items():
        patches.append(patch.object(module, attr, return_value=value))
    patches.append(patch("agents.graph.synthesize", return_value="Combined grounded answer."))

    from contextlib import ExitStack

    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        return graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})


# --- A: FINISH after one sufficient capability ---


def test_a_finish_after_one_sufficient_capability():
    actions = [
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="q"), "planner_failed": False, "planner_error": None},
        {"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None},
    ]
    final = _run_scripted_loop(
        actions,
        {(tools_module, "policy_answer"): _FAKE_RAG_RESULT, (qa_module, "check_rag_groundedness"): _FAKE_QA_PASS},
    )
    check("A: agent_status == finished (not budget-forced)", final["agent_status"] == "finished")
    check("A: termination_reason is the genuine-sufficiency reason, not a budget one", "budget" not in final["termination_reason"])
    check("A: category == POLICY (only capability actually executed)", final["category"] == "POLICY")
    check("A: exactly one tool call, no padding", final["tool_call_count"] == 1)


# --- B: planner continues when a scripted judgment says the first observation was insufficient ---


def test_b_continues_past_insufficient_first_observation():
    actions = [
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="q"), "planner_failed": False, "planner_error": None},
        {"action": PlannerAction(action="CALL_TOOL", tool="procurement_data_answer", input="q2"), "planner_failed": False, "planner_error": None},
        {"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None},
    ]
    final = _run_scripted_loop(
        actions,
        {
            (tools_module, "policy_answer"): _FAKE_RAG_RESULT,
            (tools_module, "procurement_data_answer"): _FAKE_DATA_RESULT,
            (qa_module, "check_rag_groundedness"): _FAKE_QA_FAIL,  # first observation is a FAILED check
            (qa_module, "check_sql_groundedness"): _FAKE_QA_DATA_PASS,
        },
    )
    check("B: loop is not artificially truncated after one observation", final["tool_call_count"] == 2)
    check("B: category reflects both capabilities actually executed", final["category"] == "BOTH")
    check("B: agent_status == finished", final["agent_status"] == "finished")


# --- C: a failed policy groundedness QA is rendered distinctly, and doesn't read as sufficient ---


def test_c_failed_qa_rendered_distinctly_in_observation_text():
    from agents.planner import _render_observations

    passed_text = _render_observations([{"tool": "policy_answer", "status": "completed", "answer_summary": "x", "qa_passed": True}])
    failed_text = _render_observations([{"tool": "policy_answer", "status": "completed", "answer_summary": "x", "qa_passed": False}])
    check("C: passed observation marked PASSED", "PASSED" in passed_text)
    check("C: failed observation marked FAILED, distinctly from passed", "FAILED" in failed_text and "FAILED" not in passed_text)


def test_c_and_e_finish_after_failed_qa_does_not_bypass_response_safeguard():
    # Simulates the planner's own judgment being WRONG -- it decides to FINISH right
    # after a failed groundedness check, as if that were sufficient. The system-level
    # safeguard (respond_node, reused unchanged from Step 1) must still refuse to
    # present the ungrounded answer -- FINISH cannot bypass it.
    actions = [
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="q"), "planner_failed": False, "planner_error": None},
        {"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None},
    ]
    final = _run_scripted_loop(
        actions,
        {(tools_module, "policy_answer"): _FAKE_RAG_RESULT, (qa_module, "check_rag_groundedness"): _FAKE_QA_FAIL},
    )
    check("C/E: agent_status == finished (planner did FINISH)", final["agent_status"] == "finished")
    check(
        "C/E: but the answer is the safe fallback, NOT the ungrounded tool output",
        final["answer"] == FALLBACK_MESSAGE,
        detail=repr(final["answer"]),
    )
    check("C/E: the raw ungrounded answer text never reached the user", "Policy answer text." not in (final["answer"] or ""))


# --- D: memory alone (zero tool calls) cannot produce a categorized answer ---


def test_d_memory_alone_cannot_produce_categorized_answer():
    action = PlannerAction(action="FINISH", tool=None, input=None)
    state = _base_state(
        conversation_history=[{"user": "What is our IBM spend?", "assistant": "$57.6M"}],
        called_tools=[],
    )
    with patch.object(
        planner_module, "plan_next_action", return_value={"action": action, "planner_failed": False, "planner_error": None}
    ):
        planner_result = graph_v2.planner_node(state)
    check("D: category derives to OUT_OF_SCOPE with zero tool calls, regardless of memory", planner_result["category"] == "OUT_OF_SCOPE")

    merged = {**state, **planner_result}
    route = graph_v2.route_after_planner(merged)
    check("D: routes to terminal_no_answer_node, never respond_node, on memory-only FINISH", route == "terminal_no_answer_node")


# --- category reflects capabilities actually executed, not an assumed upfront category ---


def test_category_matrix_reflects_executed_capabilities():
    cases = [
        ([], "OUT_OF_SCOPE"),
        (["policy_answer"], "POLICY"),
        (["procurement_data_answer"], "DATA"),
        (["policy_answer", "procurement_data_answer"], "BOTH"),
    ]
    for called, expected_category in cases:
        result = planner_module.derive_category(planner_module.canonicalize_tools(called))
        check(f"category matrix: called={called} -> {expected_category}", result == expected_category)


def run():
    test_a_finish_after_one_sufficient_capability()
    test_b_continues_past_insufficient_first_observation()
    test_c_failed_qa_rendered_distinctly_in_observation_text()
    test_c_and_e_finish_after_failed_qa_does_not_bypass_response_safeguard()
    test_d_memory_alone_cannot_produce_categorized_answer()
    test_category_matrix_reflects_executed_capabilities()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: {_FAILURES}")
        sys.exit(1)
    print("All semantic-FINISH tests passed.")


if __name__ == "__main__":
    run()
