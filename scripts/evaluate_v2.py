"""Targeted Step 3B evaluation harness -- distinct from scripts/evaluate.py
(which re-runs the original 15-question V1 regression set unchanged).

Two structurally distinct groups, never mixed into the same latency
aggregate:

LIVE agent tests (a1-a5): real handle_query_v2() calls against the real
model -- these test genuine LLM judgment (sufficiency decisions, memory
resolution), which a mock can't meaningfully verify. Latency/cost here is
real and noisy, same as every other live eval in this project.

DETERMINISTIC guardrail tests (b1-b4): mocked planner/tool/QA functions
driving the compiled graph through scripted scenarios -- these prove hard,
code-enforced guarantees (duplicate-call prevention, budget ceilings) that
don't depend on live-model behavior at all. They make zero real LLM/
embedding calls by construction, so their latency is not comparable to a1-5
and is excluded from the p50/p95 computed over live cases.

Writes eval/eval_results_agent.json. Run: python3 scripts/evaluate_v2.py
"""

import json
import statistics
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
from agents.orchestrator_v2 import handle_query_v2  # noqa: E402

EVAL_DIR = ROOT / "eval"

# Weights for deriving real LLM-call counts from the `steps` trace. A `steps` entry is
# NOT 1:1 with a chat-completion call: procurement_data_answer logs as one step but
# internally makes two chat calls (generate_sql + summarize_results), and
# qa_groundedness_check_data makes zero (it's deterministic, not an LLM judge).
_CHAT_CALL_WEIGHT = {
    "planner": 1,
    "policy_answer": 1,
    "procurement_data_answer": 2,
    "qa_groundedness_check_policy": 1,
    "qa_groundedness_check_data": 0,
    "synthesize": 1,
}


def _tool_sequence_from_steps(steps: list) -> list:
    return [s["step"] for s in steps if s["step"] in ("policy_answer", "procurement_data_answer")]


def _executions_per_tool(tool_sequence: list) -> dict:
    counts: dict = {}
    for t in tool_sequence:
        counts[t] = counts.get(t, 0) + 1
    return counts


def _chat_completion_count(steps: list) -> int:
    return sum(_CHAT_CALL_WEIGHT.get(s["step"], 1) for s in steps)


def _embedding_call_count(steps: list) -> int:
    # embed_query() is called once per policy_answer invocation (inside
    # rag_agent.answer_from_docs -> store.top_k_chunks), not separately logged as its
    # own step -- one embedding call per policy_answer step, by inspection of the code.
    return sum(1 for s in steps if s["step"] == "policy_answer")


def run_live_case(case: dict, resolve_history=None) -> dict:
    history = case.get("conversation_history", [])
    if resolve_history:
        history = resolve_history(history)

    response = handle_query_v2(case["query"], history)
    tool_sequence = _tool_sequence_from_steps(response["steps"])

    return {
        "id": case["id"],
        "is_live": True,
        "description": case["description"],
        "question": case["query"],
        "conversation_context": [t["user"] for t in history] or None,
        "expected_action_sequence": case["expected_tools"],
        "actual_action_sequence": tool_sequence,
        "expected_termination": "finished",
        "actual_termination": response["agent_status"],
        "planner_decisions": response["planner_decision_count"],
        "total_tool_executions": response["tool_call_count"],
        "executions_per_tool": _executions_per_tool(tool_sequence),
        "chat_completion_count": _chat_completion_count(response["steps"]),
        "embedding_call_count": _embedding_call_count(response["steps"]),
        "total_latency_ms": response["total_latency_ms"],
        "agent_status": response["agent_status"],
        "termination_reason": response["termination_reason"],
        "answer": response["answer"],
        "pass": response["agent_status"] == "finished" and set(case["expected_tools"]) <= set(tool_sequence),
    }


_FAKE_RAG_RESULT = {
    "answer": "Policy answer text.",
    "citations": [{"marker": 1, "source": "doc.pdf", "location": "page 1", "score": 0.9}],
    "chunks_used": [{"source": "doc.pdf", "location": "page 1", "text": "some text", "score": 0.9}],
}
_FAKE_DATA_RESULT = {"sql": "SELECT 1", "error": None, "answer": "Data answer text.", "columns": ["x"], "rows": [{"x": 1}]}
_FAKE_QA_PASS = {"passed": True, "score": 5, "reasoning": "ok", "method": "llm_judge"}
_FAKE_QA_DATA_PASS = {"passed": True, "reasoning": "ok", "method": "deterministic"}


def _base_state() -> dict:
    return {
        "query": "boundary test query",
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


def _deterministic_result(case_id, description, expected_termination, final_state, extra_pass=True) -> dict:
    tool_sequence = [c["tool"] for c in final_state.get("called_tools", [])]
    return {
        "id": case_id,
        "is_live": False,
        "description": description,
        "question": "(deterministic/mocked scenario -- not a live question, no real LLM calls made)",
        "conversation_context": None,
        "expected_action_sequence": None,
        "actual_action_sequence": tool_sequence,
        "expected_termination": expected_termination,
        "actual_termination": final_state["agent_status"],
        "planner_decisions": final_state["planner_decision_count"],
        "total_tool_executions": final_state["tool_call_count"],
        "executions_per_tool": _executions_per_tool(tool_sequence),
        "chat_completion_count": 0,  # all mocked -- genuinely zero real LLM calls
        "embedding_call_count": 0,
        "total_latency_ms": None,  # not meaningful for a mocked run -- excluded from aggregation
        "agent_status": final_state["agent_status"],
        "termination_reason": final_state["termination_reason"],
        "answer": final_state.get("answer"),
        "pass": (final_state["agent_status"] == expected_termination) and extra_pass,
    }


def duplicate_prevention_case() -> dict:
    actions = [
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="approval policy"), "planner_failed": False, "planner_error": None},
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input="approval policy"), "planner_failed": False, "planner_error": None},  # exact duplicate -- blocked
        {"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None},
    ]
    it = iter(actions)
    with patch.object(planner_module, "plan_next_action", side_effect=lambda *a, **kw: next(it)), patch.object(
        tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT
    ), patch.object(qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS), patch(
        "agents.graph.synthesize", return_value="Combined."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})
    result = _deterministic_result(
        "b1", "duplicate-call prevention (identical tool+input blocked)", "finished", final_state,
        extra_pass=final_state["tool_call_count"] == 1,
    )
    result["expected_action_sequence"] = ["policy_answer"]
    return result


def per_tool_boundary_case() -> dict:
    actions = [
        {"action": PlannerAction(action="CALL_TOOL", tool="policy_answer", input=f"distinct input {i}"), "planner_failed": False, "planner_error": None}
        for i in range(graph_v2.MAX_EXECUTIONS_PER_TOOL + 2)
    ] + [{"action": PlannerAction(action="FINISH"), "planner_failed": False, "planner_error": None}]
    it = iter(actions)
    with patch.object(planner_module, "plan_next_action", side_effect=lambda *a, **kw: next(it)), patch.object(
        tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT
    ), patch.object(qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS), patch(
        "agents.graph.synthesize", return_value="Combined."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})
    result = _deterministic_result(
        "b2", f"per-tool execution boundary (max {graph_v2.MAX_EXECUTIONS_PER_TOOL})", "finished", final_state,
        extra_pass=[c["tool"] for c in final_state["called_tools"]].count("policy_answer") == graph_v2.MAX_EXECUTIONS_PER_TOOL,
    )
    result["expected_action_sequence"] = ["policy_answer"] * graph_v2.MAX_EXECUTIONS_PER_TOOL
    return result


def _alternating_planner(*args, **kwargs):
    n = len(args[3])
    tool = "policy_answer" if n % 2 == 0 else "procurement_data_answer"
    return {"action": PlannerAction(action="CALL_TOOL", tool=tool, input=f"distinct input {n}"), "planner_failed": False, "planner_error": None}


def global_tool_boundary_case() -> dict:
    with patch.object(planner_module, "plan_next_action", side_effect=_alternating_planner), patch.object(
        tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT
    ), patch.object(tools_module, "procurement_data_answer", return_value=_FAKE_DATA_RESULT), patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ), patch.object(
        qa_module, "check_sql_groundedness", return_value=_FAKE_QA_DATA_PASS
    ), patch(
        "agents.graph.synthesize", return_value="Combined."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})
    return _deterministic_result(
        "b3", f"global tool-execution boundary (max {graph_v2.MAX_TOOL_EXECUTIONS})", "budget_exhausted", final_state,
        extra_pass=final_state["tool_call_count"] <= graph_v2.MAX_TOOL_EXECUTIONS,
    )


def planner_decision_boundary_case() -> dict:
    with patch.object(planner_module, "plan_next_action", side_effect=_alternating_planner), patch.object(
        tools_module, "policy_answer", return_value=_FAKE_RAG_RESULT
    ), patch.object(tools_module, "procurement_data_answer", return_value=_FAKE_DATA_RESULT), patch.object(
        qa_module, "check_rag_groundedness", return_value=_FAKE_QA_PASS
    ), patch.object(
        qa_module, "check_sql_groundedness", return_value=_FAKE_QA_DATA_PASS
    ), patch(
        "agents.graph.synthesize", return_value="Combined."
    ):
        final_state = graph_v2.AGENT_GRAPH.invoke(_base_state(), config={"recursion_limit": 30})
    return _deterministic_result(
        "b4", f"planner-decision boundary (max {graph_v2.MAX_PLANNER_DECISIONS})", "budget_exhausted", final_state,
        extra_pass=final_state["planner_decision_count"] <= graph_v2.MAX_PLANNER_DECISIONS,
    )


def run():
    cases = json.loads((EVAL_DIR / "eval_questions_agent.json").read_text())
    by_id = {c["id"]: c for c in cases}
    live_results = []
    deterministic_results = []

    print("[a1] early FINISH after one tool...")
    r1 = run_live_case(by_id["a1"])
    live_results.append(r1)

    print("[a2] two-tool observation-driven sequence...")
    live_results.append(run_live_case(by_id["a2"]))

    print("[a3] legitimate refinement (best-effort live probe)...")
    live_results.append(run_live_case(by_id["a3"]))

    print("[a4] memory-dependent follow-up...")
    live_results.append(run_live_case(by_id["a4"], resolve_history=lambda h: [{"user": h[0]["user"], "assistant": r1["answer"]}]))

    print("[a5] memory as context, not evidence...")
    live_results.append(run_live_case(by_id["a5"], resolve_history=lambda h: [{"user": h[0]["user"], "assistant": r1["answer"]}]))

    print("[b1] duplicate-call prevention (deterministic)...")
    deterministic_results.append(duplicate_prevention_case())

    print("[b2] per-tool execution boundary (deterministic)...")
    deterministic_results.append(per_tool_boundary_case())

    print("[b3] global tool-execution boundary (deterministic)...")
    deterministic_results.append(global_tool_boundary_case())

    print("[b4] planner-decision boundary (deterministic)...")
    deterministic_results.append(planner_decision_boundary_case())

    all_results = live_results + deterministic_results
    n_pass = sum(1 for r in all_results if r["pass"])

    live_latencies = [r["total_latency_ms"] for r in live_results]
    latency_summary = {
        "n_live_cases": len(live_latencies),
        "p50_latency_ms": round(statistics.median(live_latencies)) if live_latencies else None,
        "p95_latency_ms": round(sorted(live_latencies)[max(0, round(0.95 * len(live_latencies)) - 1)]) if live_latencies else None,
    }

    output = {
        "live_results": live_results,
        "deterministic_results": deterministic_results,
        "summary": {"n_cases": len(all_results), "n_pass": n_pass, "n_fail": len(all_results) - n_pass},
        "live_latency_summary": latency_summary,
    }
    (EVAL_DIR / "eval_results_agent.json").write_text(json.dumps(output, indent=2, default=str))

    def _print_table(title, results, show_latency):
        print(f"\n{title}")
        print("=" * 110)
        if show_latency:
            print(f"{'id':4} {'description':40} {'term':16} {'decisions':10} {'tools':6} {'chat':5} {'embed':6} {'ms':7} PASS")
        else:
            print(f"{'id':4} {'description':40} {'expected':16} {'actual':16} {'decisions':10} {'tools':6} PASS")
        print("=" * 110)
        for r in results:
            if show_latency:
                print(
                    f"{r['id']:4} {r['description'][:40]:40} {r['actual_termination']:16} "
                    f"{r['planner_decisions']:<10} {r['total_tool_executions']:<6} {r['chat_completion_count']:<5} "
                    f"{r['embedding_call_count']:<6} {r['total_latency_ms']:<7} {'PASS' if r['pass'] else 'FAIL'}"
                )
            else:
                print(
                    f"{r['id']:4} {r['description'][:40]:40} {r['expected_termination']:16} {r['actual_termination']:16} "
                    f"{r['planner_decisions']:<10} {r['total_tool_executions']:<6} {'PASS' if r['pass'] else 'FAIL'}"
                )

    _print_table("LIVE AGENT TESTS (a1-a5) -- real model calls", live_results, show_latency=True)
    _print_table("DETERMINISTIC GUARDRAIL TESTS (b1-b4) -- mocked, zero real LLM calls", deterministic_results, show_latency=False)

    print("\n" + "=" * 60)
    print("LIVE LATENCY SUMMARY (a1-a5 only -- deterministic cases excluded)")
    print("=" * 60)
    for k, v in latency_summary.items():
        print(f"{k:20} {v}")

    print(f"\n{n_pass}/{len(all_results)} passed overall")


if __name__ == "__main__":
    run()
