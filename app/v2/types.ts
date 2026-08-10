// V2-specific types, kept separate from ../types.ts (V1's contract) so V1's types are
// never touched by V2's evolution. V2ChatResponse is a superset of V1's ChatResponse
// fields plus the new agent-loop/trace fields -- intentionally duplicated field names
// (not extending ChatResponse) so each contract can be read on its own without cross-
// referencing the other file.

export type Category = "POLICY" | "DATA" | "BOTH" | "OUT_OF_SCOPE";

export interface Citation {
  marker: number;
  source: string;
  location: string;
  score: number;
}

export interface GroundednessResult {
  path: "policy" | "data";
  passed: boolean;
  score?: number;
  reasoning: string;
  method: "llm_judge" | "deterministic";
}

export interface PipelineStep {
  step: string;
  latency_ms: number;
  detail?: Record<string, unknown>;
  error?: string;
}

export type AgentStatus = "in_progress" | "finished" | "budget_exhausted" | "planner_failed" | "tool_failed";

export interface TraceEvent {
  iteration: number | null;
  event:
    | "memory_context"
    | "planner_decision"
    | "tool_call"
    | "observation_recorded"
    | "duplicate_blocked"
    | "per_tool_limit_blocked"
    | "qa_result"
    | "finish"
    | "budget_exhausted"
    | "failure"
    | "status";
  label: string;
  status?: "completed" | "failed" | "passed" | "blocked" | null;
  // The model's own brief, stated rationale for this decision -- not a mechanistic
  // readout of its internal computation, just a one-turn explanation surfaced for
  // demo/interpretability purposes. See PlannerAction in api/agents/contracts.py.
  reasoning?: string | null;
}

export interface V2ChatResponse {
  query: string;
  category: Category;
  steps: PipelineStep[];
  answer: string;
  citations: Citation[];
  unverified_citations: Citation[];
  sql: string | null;
  sql_columns: string[];
  sql_rows: Record<string, unknown>[];
  groundedness: GroundednessResult[];
  total_latency_ms: number;
  agent_status: AgentStatus;
  termination_reason: string | null;
  planner_decision_count: number;
  tool_call_count: number;
  agent_trace: TraceEvent[];
  error?: string;
}

export interface V2ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: V2ChatResponse;
}

// Wire format sent to /api/v2/chat -- explicit paired turns, not a flat message list.
export interface ConversationTurn {
  user: string;
  assistant: string;
}
