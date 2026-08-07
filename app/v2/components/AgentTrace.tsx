"use client";

import { useState } from "react";
import type { AgentStatus, TraceEvent } from "../types";

// Styled after app/components/PipelineTrace.tsx's collapsible pattern. Renders only
// the structured TraceEvent list the API returns -- there is no raw model reasoning,
// prompt text, or hidden chain-of-thought anywhere in this component's props, by
// construction (see api/agents/trace.py's build_trace()).

const AGENT_STATUS_LABEL: Record<AgentStatus, string> = {
  in_progress: "In progress",
  finished: "Finished",
  budget_exhausted: "Budget exhausted",
  planner_failed: "Planner failed",
  tool_failed: "Tool failed",
};

function groupByIteration(events: TraceEvent[]): { iteration: number | null; events: TraceEvent[] }[] {
  const groups: { iteration: number | null; events: TraceEvent[] }[] = [];
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
  totalMs,
}: {
  agentStatus: AgentStatus;
  terminationReason: string | null;
  plannerDecisionCount: number;
  toolCallCount: number;
  events: TraceEvent[];
  totalMs: number;
}) {
  const [open, setOpen] = useState(false);
  const groups = groupByIteration(events);

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
                      {e.label}
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
