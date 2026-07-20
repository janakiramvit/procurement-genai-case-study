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
  detail?: { category: Category; reasoning: string };
}

export interface ChatResponse {
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
  error?: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  response?: ChatResponse;
}
