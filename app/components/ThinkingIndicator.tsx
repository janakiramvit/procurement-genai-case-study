"use client";

import { useEffect, useState } from "react";

// Cosmetic only -- the backend returns one complete response, it doesn't stream
// intermediate state. This cycles through the pipeline stages a multi-agent
// system like this actually runs, so the wait reads as "working," not "stuck."
// See DESIGN.md for why we chose a full-response API over SSE streaming.
const STAGES = ["Routing question…", "Retrieving policy docs / querying spend data…", "Verifying groundedness…", "Composing answer…"];

export function ThinkingIndicator() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 1400);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex justify-start">
      <div className="flex items-center gap-2 rounded-2xl bg-white px-4 py-3 text-sm text-slate-500 shadow-sm">
        <span className="flex gap-1">
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-novartis-blue [animation-delay:-0.3s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-novartis-blue [animation-delay:-0.15s]" />
          <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-novartis-blue" />
        </span>
        {STAGES[stage]}
      </div>
    </div>
  );
}
