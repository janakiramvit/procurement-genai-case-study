"""Deterministic unit tests for Step 3B's safe execution-trace projection.

No API calls -- build_trace() is a pure function over hand-crafted state.

Run directly: python3 tests/test_trace.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "api"))

from agents.contracts import PlannerAction  # noqa: E402
from agents.trace import TraceEvent, build_trace  # noqa: E402

_FAILURES = []


def check(name: str, condition: bool, detail: str = ""):
    status = "PASS" if condition else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not condition else ""))
    if not condition:
        _FAILURES.append(name)


def _state_two_tools_sequential():
    return {
        "conversation_history": [],
        "actions_taken": [
            {"decision_number": 1, "action": "CALL_TOOL", "tool": "procurement_data_answer", "input": "IBM spend", "status": "executed"},
            {"decision_number": 2, "action": "CALL_TOOL", "tool": "policy_answer", "input": "approval policy", "status": "executed"},
            {"decision_number": 3, "action": "FINISH", "tool": None, "input": None, "status": "genuine"},
        ],
        "observations": [
            {"decision_number": 1, "tool": "procurement_data_answer", "status": "completed", "answer_summary": "IBM spend = $57.6M", "qa_passed": True, "qa_method": "deterministic"},
            {"decision_number": 2, "tool": "policy_answer", "status": "completed", "answer_summary": "Executive approval required", "qa_passed": True, "qa_method": "llm_judge"},
        ],
        "agent_status": "finished",
        "termination_reason": "planner determined sufficient evidence",
    }


def test_event_ordering():
    events = build_trace(_state_two_tools_sequential())
    order = [e.event for e in events]
    expected = [
        "planner_decision", "tool_call", "qa_result", "observation_recorded",
        "planner_decision", "tool_call", "qa_result", "observation_recorded",
        "finish", "status",
    ]
    check("event ordering matches expected sequence", order == expected, detail=str(order))


def test_qa_labels_match_correction_7_terminology():
    events = build_trace(_state_two_tools_sequential())
    qa_events = [e for e in events if e.event == "qa_result"]
    check("data path uses 'Data Result Validation' label", "Data Result Validation" in qa_events[0].label)
    check("policy path uses 'Policy Groundedness QA' label", "Policy Groundedness QA" in qa_events[1].label)
    check("data label does NOT say 'groundedness'", "groundedness" not in qa_events[0].label.lower())


def test_finish_event_present():
    events = build_trace(_state_two_tools_sequential())
    check("a genuine finish event is present", any(e.event == "finish" for e in events))


def test_failure_event_present():
    state = {
        "conversation_history": [],
        "actions_taken": [{"decision_number": 1, "action": "FINISH", "tool": None, "input": None, "status": "failed"}],
        "observations": [],
        "agent_status": "planner_failed",
        "termination_reason": "planner call failed",
    }
    events = build_trace(state)
    check("failure -> status event uses event type 'failure'", events[-1].event == "failure")
    check("failure -> label mentions planner_failed", "planner_failed" in events[-1].label)


def test_budget_exhausted_event():
    state = {
        "conversation_history": [],
        "actions_taken": [
            {"decision_number": 1, "action": "CALL_TOOL", "tool": "policy_answer", "input": "x", "status": "executed"},
            {"decision_number": 2, "action": "FINISH", "tool": None, "input": None, "status": "forced"},
        ],
        "observations": [
            {"decision_number": 1, "tool": "policy_answer", "status": "completed", "answer_summary": "x", "qa_passed": True, "qa_method": "llm_judge"},
        ],
        "agent_status": "budget_exhausted",
        "termination_reason": "max planner decisions (7) reached",
    }
    events = build_trace(state)
    check("budget-exhausted event present", any(e.event == "budget_exhausted" for e in events))


def test_memory_used_event():
    state = _state_two_tools_sequential()
    state["conversation_history"] = [{"user": "a", "assistant": "b"}, {"user": "c", "assistant": "d"}]
    events = build_trace(state)
    check("memory_context is the first event when history is present", events[0].event == "memory_context")
    check("memory_context label reports the correct turn count", "2 prior turns supplied" in events[0].label)

    no_history = build_trace(_state_two_tools_sequential())
    check("no memory_context event when history is empty", not any(e.event == "memory_context" for e in no_history))


def test_no_raw_reasoning_or_prompt_fields_can_appear():
    # Structural guarantee, not just a convention: TraceEvent's schema has no field
    # that could hold free-form reasoning or prompt text, and PlannerAction itself
    # (contracts.py) has no `reasoning` field at all to leak in the first place.
    check("PlannerAction has no reasoning field", not hasattr(PlannerAction(action="FINISH"), "reasoning"))
    check(
        "TraceEvent's fields are exactly the safe set",
        set(TraceEvent.model_fields.keys()) == {"iteration", "event", "label", "status"},
    )
    events = build_trace(_state_two_tools_sequential())
    for e in events:
        dumped = e.model_dump()
        check(
            f"event {e.event} dump has no unexpected keys",
            set(dumped.keys()) <= {"iteration", "event", "label", "status"},
        )


def run():
    test_event_ordering()
    test_qa_labels_match_correction_7_terminology()
    test_finish_event_present()
    test_failure_event_present()
    test_budget_exhausted_event()
    test_memory_used_event()
    test_no_raw_reasoning_or_prompt_fields_can_appear()

    print()
    if _FAILURES:
        print(f"{len(_FAILURES)} FAILED: {_FAILURES}")
        sys.exit(1)
    print("All deterministic trace tests passed.")


if __name__ == "__main__":
    run()
