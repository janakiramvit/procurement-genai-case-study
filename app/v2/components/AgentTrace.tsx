"use client";

import { useState } from "react";
import type { AgentStatus, GroundednessResult, TraceEvent } from "../types";

// Styled after app/components/PipelineTrace.tsx's collapsible pattern. Renders only
// the structured TraceEvent list (plus the existing `groundedness` field, both already
// part of the V2 API response) the API returns -- there is no raw model reasoning,
// prompt text, or hidden chain-of-thought anywhere in this component's props, by
// construction (see api/agents/trace.py's build_trace()).
//
// formatTraceEvent() below is a presentation-only relabeling pass: it maps the backend's
// existing event/label/status fields onto the Plan -> Act -> Verify -> Observe -> Finish
// wording, using only data already present in the API response. It does not add any new
// backend field -- the policy QA score, when shown, is read from the existing
// `groundedness` response field (unchanged), correlated to the right VERIFY line by
// chronological order (both `groundedness` and the trace's qa_result events are appended
// in the same per-iteration sequence server-side, so positional pairing is exact).

const AGENT_STATUS_LABEL: Record<AgentStatus, string> = {
  in_progress: "In progress",
  finished: "Finished",
  budget_exhausted: "Budget exhausted",
  planner_failed: "Planner failed",
  tool_failed: "Tool failed",
};

const TOOL_DISPLAY_NAME: Record<string, string> = {
  policy_answer: "Policy Retrieval",
  procurement_data_answer: "Procurement Spend Query",
};

function toolFromPlannerLabel(label: string): string | null {
  const match = label.match(/Planner → (policy_answer|procurement_data_answer)/);
  return match ? match[1] : null;
}

interface DisplayEvent {
  iteration: number | null;
  text: string;
  status: TraceEvent["status"];
}

function formatTraceEvents(events: TraceEvent[], groundedness: GroundednessResult[], toolCallCount: number): DisplayEvent[] {
  const policyGroundedness = groundedness.filter((g) => g.path === "policy");
  let policyIdx = 0;
  let currentTool: string | null = null;

  return events.map((e): DisplayEvent => {
    if (e.event === "planner_decision") {
      currentTool = toolFromPlannerLabel(e.label);
      const display = currentTool ? TOOL_DISPLAY_NAME[currentTool] : e.label;
      return { iteration: e.iteration, text: `PLAN — Planner selected ${display}`, status: e.status };
    }

    if (e.event === "tool_call") {
      const display = currentTool ? TOOL_DISPLAY_NAME[currentTool] : "Tool";
      const verb = e.status === "failed" ? "failed" : "completed";
      return { iteration: e.iteration, text: `ACT — ${display} ${verb}`, status: e.status };
    }

    if (e.event === "qa_result") {
      const passLabel = e.status === "passed" ? "PASS" : "FAIL";
      if (currentTool === "policy_answer") {
        const g = policyGroundedness[policyIdx++];
        const scoreSuffix = g && typeof g.score === "number" ? ` (score ${g.score}/5)` : "";
        return { iteration: e.iteration, text: `VERIFY — Policy Groundedness QA: ${passLabel}${scoreSuffix}`, status: e.status };
      }
      if (currentTool === "procurement_data_answer") {
        return { iteration: e.iteration, text: `VERIFY — Data Result Validation: ${passLabel}`, status: e.status };
      }
      return { iteration: e.iteration, text: e.label, status: e.status };
    }

    if (e.event === "observation_recorded") {
      return { iteration: e.iteration, text: "OBSERVE — Tool result recorded for the next planner decision", status: e.status };
    }

    if (e.event === "finish") {
      // Deliberately avoids asserting an internal judgment ("determined... sufficient")
      // the system has no way to observe -- PlannerAction carries no reasoning field, so
      // FINISH is only ever an observable action, never a verified conclusion. Wording
      // states the mechanical fact only, chosen from the existing toolCallCount field,
      // and does not claim evidence was collected when nothing was actually executed
      // this turn (a genuine zero-tool FINISH -- e.g. out-of-scope).
      const text =
        toolCallCount > 0
          ? "FINISH — Planner selected FINISH after reviewing available observations"
          : "FINISH — Planner selected FINISH without calling a procurement capability";
      return { iteration: e.iteration, text, status: e.status };
    }

    // memory_context, duplicate_blocked, per_tool_limit_blocked, budget_exhausted,
    // failure, status: preserved unchanged -- out of the requested relabeling scope.
    return { iteration: e.iteration, text: e.label, status: e.status };
  });
}

function groupByIteration(events: DisplayEvent[]): { iteration: number | null; events: DisplayEvent[] }[] {
  const groups: { iteration: number | null; events: DisplayEvent[] }[] = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    if (last && last.iteration === e.iteration) {
      last.events.push(e);
    } else {
      groups.push({ iteration: e.iteration, events: [e] });
    }
  }
  return groups;
}

export function AgentTrace({
  agentStatus,
  terminationReason,
  plannerDecisionCount,
  toolCallCount,
  events,
  groundedness,
  totalMs,
}: {
  agentStatus: AgentStatus;
  terminationReason: string | null;
  plannerDecisionCount: number;
  toolCallCount: number;
  events: TraceEvent[];
  groundedness: GroundednessResult[];
  totalMs: number;
}) {
  const [open, setOpen] = useState(false);
  const displayEvents = formatTraceEvents(events, groundedness, toolCallCount);
  const groups = groupByIteration(displayEvents);

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 font-medium text-slate-600 hover:text-slate-900"
      >
        <span>
          <span className="rounded bg-novartis-blue/10 px-1.5 py-0.5 text-novartis-darkblue">
            {AGENT_STATUS_LABEL[agentStatus]}
          </span>{" "}
          · {plannerDecisionCount} planner decision{plannerDecisionCount === 1 ? "" : "s"} · {toolCallCount} tool
          call{toolCallCount === 1 ? "" : "s"} · {totalMs}ms
        </span>
        <span>{open ? "hide execution trace ▲" : "show execution trace ▼"}</span>
      </button>
      {open && (
        <div className="space-y-3 border-t border-slate-200 px-3 py-2">
          {groups.map((g, gi) => (
            <div key={gi}>
              {g.iteration !== null && (
                <div className="mb-1 font-semibold text-slate-500">Iteration {g.iteration}</div>
              )}
              <div className="space-y-1">
                {g.events.map((e, ei) => (
                  <div
                    key={ei}
                    className={`flex items-center justify-between rounded px-2 py-1 ${
                      e.status === "passed"
                        ? "bg-green-50 text-green-700"
                        : e.status === "failed" || e.status === "blocked"
                          ? "bg-amber-50 text-amber-700"
                          : "text-slate-600"
                    }`}
                  >
                    <span>
                      {e.status === "passed" ? "✓ " : e.status === "failed" ? "✗ " : e.status === "blocked" ? "⚠ " : ""}
                      {e.text}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {terminationReason && (
            <div className="border-t border-slate-200 pt-2 text-slate-500">Termination reason: {terminationReason}</div>
          )}
        </div>
      )}
    </div>
  );
}
