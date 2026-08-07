import { EvidenceSection } from "../../components/EvidenceSection";
import { SqlBlock } from "../../components/SqlBlock";
import type { V2ChatMessage } from "../types";
import { AgentTrace } from "./AgentTrace";

// Parallel to app/components/MessageBubble.tsx -- reuses the same evidence/SQL
// rendering (shared, unmodified) but swaps PipelineTrace for AgentTrace.
export function V2MessageBubble({ message }: { message: V2ChatMessage }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
          isUser ? "bg-novartis-blue text-white" : "bg-white text-slate-800"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {!isUser && message.response && (
          <>
            <EvidenceSection citations={message.response.citations} />
            <EvidenceSection citations={message.response.unverified_citations} variant="unverified" />

            {message.response.sql && (
              <SqlBlock
                sql={message.response.sql}
                columns={message.response.sql_columns}
                rows={message.response.sql_rows}
              />
            )}

            <AgentTrace
              agentStatus={message.response.agent_status}
              terminationReason={message.response.termination_reason}
              plannerDecisionCount={message.response.planner_decision_count}
              toolCallCount={message.response.tool_call_count}
              events={message.response.agent_trace}
              totalMs={message.response.total_latency_ms}
            />
          </>
        )}
      </div>
    </div>
  );
}
