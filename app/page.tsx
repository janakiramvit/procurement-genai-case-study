"use client";

import { useRef, useState } from "react";
import type { ChatMessage, ChatResponse } from "./types";
import { MessageBubble } from "./components/MessageBubble";
import { ThinkingIndicator } from "./components/ThinkingIndicator";

const SAMPLE_QUESTIONS = [
  "I want to buy laptops in USA for USD 70k, do I need a contract or a PO or do I need to engage procurement?",
  "I want to add a supplier to the current sourcing event, how can I do it?",
  "What is our total spend with IBM?",
  "What's the correct UNSPSC code for notebook computers?",
];

export default function Home() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  async function send(query: string) {
    if (!query.trim() || loading) return;
    setMessages((m) => [...m, { role: "user", content: query }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });
      const data: ChatResponse = await res.json();
      if (!res.ok) {
        setMessages((m) => [...m, { role: "assistant", content: `Error: ${data.error ?? "request failed"}` }]);
      } else {
        setMessages((m) => [...m, { role: "assistant", content: data.answer, response: data }]);
      }
    } catch (err) {
      setMessages((m) => [...m, { role: "assistant", content: `Network error: ${String(err)}` }]);
    } finally {
      setLoading(false);
      setTimeout(() => scrollRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  return (
    <main className="mx-auto flex h-screen max-w-3xl flex-col px-4 py-6">
      <header className="mb-4">
        <h1 className="text-xl font-semibold text-novartis-darkblue">Procurement Copilot</h1>
        <p className="text-sm text-slate-500">
          L1 AI helpdesk over procurement policy documents and spend / PO data · multi-agent · citations + QA gated
        </p>
      </header>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-xl bg-slate-100 p-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-slate-500">Try one of these, or ask your own question:</p>
            <div className="flex flex-wrap gap-2">
              {SAMPLE_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => send(q)}
                  className="rounded-full border border-novartis-blue/30 bg-white px-3 py-1.5 text-xs text-novartis-darkblue hover:bg-novartis-blue/5"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <MessageBubble key={i} message={m} />
        ))}
        {loading && <ThinkingIndicator />}
        <div ref={scrollRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-4 flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about procurement policy, Ariba, UNSPSC codes, or spend data…"
          className="flex-1 rounded-full border border-slate-300 px-4 py-2 text-sm outline-none focus:border-novartis-blue"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-full bg-novartis-blue px-5 py-2 text-sm font-medium text-white hover:bg-novartis-darkblue disabled:opacity-50"
        >
          Send
        </button>
      </form>
    </main>
  );
}
