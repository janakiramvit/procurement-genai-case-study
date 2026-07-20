import type { ChatMessage } from "../types";
import { PipelineTrace } from "./PipelineTrace";
import { SqlBlock } from "./SqlBlock";

export function MessageBubble({ message }: { message: ChatMessage }) {
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
            {message.response.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {message.response.citations.map((c) => (
                  <span
                    key={c.marker}
                    title={`similarity ${c.score}`}
                    className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500"
                  >
                    [{c.marker}] {c.source} · {c.location}
                  </span>
                ))}
              </div>
            )}

            {message.response.sql && (
              <SqlBlock
                sql={message.response.sql}
                columns={message.response.sql_columns}
                rows={message.response.sql_rows}
              />
            )}

            <PipelineTrace
              category={message.response.category}
              steps={message.response.steps}
              groundedness={message.response.groundedness}
              totalMs={message.response.total_latency_ms}
            />
          </>
        )}
      </div>
    </div>
  );
}
