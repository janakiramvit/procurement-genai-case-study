"use client";

import { useState } from "react";
import type { Category, PipelineStep, GroundednessResult } from "../types";

const STEP_LABELS: Record<string, string> = {
  router: "Routing question",
  rag_retrieve_and_answer: "Retrieving policy docs",
  qa_groundedness_check_policy: "Verifying policy answer",
  sql_generate_execute_and_answer: "Querying spend / PO data",
  qa_groundedness_check_data: "Verifying data answer",
  synthesize: "Combining answers",
};

const CATEGORY_LABEL: Record<Category, string> = {
  POLICY: "Policy (RAG)",
  DATA: "Data (SQL)",
  BOTH: "Policy + Data",
  OUT_OF_SCOPE: "Out of scope",
};

export function PipelineTrace({
  category,
  steps,
  groundedness,
  totalMs,
}: {
  category: Category;
  steps: PipelineStep[];
  groundedness: GroundednessResult[];
  totalMs: number;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 font-medium text-slate-600 hover:text-slate-900"
      >
        <span>
          <span className="rounded bg-novartis-blue/10 px-1.5 py-0.5 text-novartis-darkblue">
            {CATEGORY_LABEL[category]}
          </span>{" "}
          · {steps.length} step{steps.length === 1 ? "" : "s"} · {totalMs}ms
        </span>
        <span>{open ? "hide pipeline ▲" : "show pipeline ▼"}</span>
      </button>
      {open && (
        <div className="space-y-1 border-t border-slate-200 px-3 py-2">
          {steps.map((s, i) => (
            <div key={i} className="flex items-center justify-between text-slate-500">
              <span>{STEP_LABELS[s.step] ?? s.step}</span>
              <span className="tabular-nums">{s.latency_ms}ms</span>
            </div>
          ))}
          {groundedness.map((g, i) => (
            <div
              key={`qa-${i}`}
              className={`mt-1 flex items-center justify-between rounded px-2 py-1 ${
                g.passed ? "bg-green-50 text-green-700" : "bg-amber-50 text-amber-700"
              }`}
            >
              <span>
                {g.passed ? "✓" : "⚠"} {g.path} QA ({g.method === "llm_judge" ? "LLM judge" : "deterministic"}
                {g.score ? `, score ${g.score}/5` : ""})
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
