"""Safe execution-trace projection -- Step 3B.

build_trace() is a pure function over already-structured state
(actions_taken / observations / conversation_history / agent_status /
termination_reason). It never touches raw LLM messages or prompt text --
the only model-generated free text it can surface is PlannerAction.reasoning
(see contracts.py), a deliberately bounded, one-turn, non-fed-back
explanation string threaded through actions_taken. There is no code path
through which raw prompts or a genuine chain-of-thought could reach a
TraceEvent.

QA labels are deliberately different per capability, per the actual
implementation in qa.py: "Policy Groundedness QA" for the real LLM-judge
check (check_rag_groundedness), "Data Result Validation" for the purely
deterministic error-check (check_sql_groundedness) -- the data path is never
represented as a semantic groundedness verifier, because it isn't one.
"""

from typing import Literal, Optional

from pydantic import BaseModel

QA_LABEL_BY_TOOL = {
    "policy_answer": "Policy Groundedness QA",
    "procurement_data_answer": "Data Result Validation",
}


class TraceEvent(BaseModel):
    iteration: Optional[int] = None
    event: Literal[
        "memory_context",
        "planner_decision",
        "tool_call",
        "observation_recorded",
        "duplicate_blocked",
        "per_tool_limit_blocked",
        "qa_result",
        "finish",
        "budget_exhausted",
        "failure",
        "status",
    ]
    label: str
    status: Optional[Literal["completed", "failed", "passed", "blocked"]] = None
    reasoning: Optional[str] = None


def build_trace(final_state: dict) -> list[TraceEvent]:
    events: list[TraceEvent] = []

    history = final_state.get("conversation_history") or []
    if history:
        events.append(
            TraceEvent(
                event="memory_context",
                label=f"Conversation Context → {len(history)} prior turn{'s' if len(history) != 1 else ''} supplied",
            )
        )

    observations_by_decision = {o["decision_number"]: o for o in final_state.get("observations", [])}

    for a in final_state.get("actions_taken", []):
        n = a["decision_number"]

        if a["action"] == "CALL_TOOL":
            if a["status"] == "executed":
                events.append(
                    TraceEvent(
                        iteration=n,
                        event="planner_decision",
                        label=f"Planner → {a['tool']}",
                        reasoning=a.get("reasoning"),
                    )
                )
                obs = observations_by_decision.get(n)
                if obs:
                    tool_ok = obs["status"] == "completed"
                    events.append(
                        TraceEvent(
                            iteration=n,
                            event="tool_call",
                            label=f"Tool → {'completed' if tool_ok else 'failed'}",
                            status="completed" if tool_ok else "failed",
                        )
                    )
                    if obs.get("qa_passed") is not None:
                        qa_label = QA_LABEL_BY_TOOL.get(a["tool"], "Result Validation")
                        events.append(
                            TraceEvent(
                                iteration=n,
                                event="qa_result",
                                label=f"{qa_label} → {'PASS' if obs['qa_passed'] else 'FAIL'}",
                                status="passed" if obs["qa_passed"] else "failed",
                            )
                        )
                    events.append(TraceEvent(iteration=n, event="observation_recorded", label="Observation recorded"))
            elif a["status"] == "blocked_duplicate":
                events.append(
                    TraceEvent(
                        iteration=n,
                        event="duplicate_blocked",
                        label=f"Planner → {a['tool']} (blocked: identical call already made this turn)",
                        status="blocked",
                        reasoning=a.get("reasoning"),
                    )
                )
            elif a["status"] == "blocked_per_tool_limit":
                events.append(
                    TraceEvent(
                        iteration=n,
                        event="per_tool_limit_blocked",
                        label=f"Planner → {a['tool']} (blocked: per-capability limit reached)",
                        status="blocked",
                        reasoning=a.get("reasoning"),
                    )
                )
        elif a["action"] == "FINISH":
            if a["status"] == "forced":
                events.append(
                    TraceEvent(iteration=n, event="budget_exhausted", label="Planner → FINISH (budget exhausted)")
                )
            else:
                events.append(
                    TraceEvent(iteration=n, event="finish", label="Planner → FINISH", reasoning=a.get("reasoning"))
                )

    agent_status = final_state.get("agent_status")
    termination_reason = final_state.get("termination_reason")
    status_event = "failure" if agent_status in ("planner_failed", "tool_failed") else "status"
    events.append(
        TraceEvent(
            event=status_event,
            label=f"Status → {agent_status}" + (f" ({termination_reason})" if termination_reason else ""),
        )
    )

    return events
