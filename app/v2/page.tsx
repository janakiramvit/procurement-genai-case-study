"use client";

import { useEffect, useRef, useState } from "react";
import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { SuggestedQuestions } from "../components/SuggestedQuestions";
import { ThinkingIndicator } from "../components/ThinkingIndicator";
import type { ConversationTurn, V2ChatMessage, V2ChatResponse } from "./types";
import { V2MessageBubble } from "./components/V2MessageBubble";

const SESSION_STORAGE_KEY = "procurement-copilot-v2-messages";
const MAX_MEMORY_TURNS = 10; // 1 turn = one user message + its assistant response

const SAMPLE_QUESTIONS = [
  "What approvals or contract requirements apply given our total spend with IBM?",
  "What is our total spend with IBM?",
  "What is the approval policy for large purchases?",
  "I want to buy laptops in USA for USD 70k, do I need a contract or a PO?",
];

// Client-side memory: sessionStorage (tab-scoped, survives refresh, cleared by New Chat
// or when the tab closes -- no backend session store, no server-side persistence at all).
function loadMessages(): V2ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.sessionStorage.getItem(SESSION_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as V2ChatMessage[]) : [];
  } catch {
    return [];
  }
}

function saveMessages(messages: V2ChatMessage[]) {
  try {
    window.sessionStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(messages));
  } catch {
    // sessionStorage unavailable/full -- memory degrades to in-page-only for this
    // session rather than breaking the chat.
  }
}

// Pairs the flat visible transcript into user+assistant turns and keeps only the last
// MAX_MEMORY_TURNS complete pairs -- the visible transcript itself may be longer than
// this; only this bounded slice is ever sent to the agent as memory. The server
// independently re-validates/re-truncates this regardless (see api/agents/memory.py).
function deriveConversationHistory(messages: V2ChatMessage[]): ConversationTurn[] {
  const turns: ConversationTurn[] = [];
  for (let i = 0; i < messages.length - 1; i++) {
    if (messages[i].role === "user" && messages[i + 1].role === "assistant") {
      turns.push({ user: messages[i].content, assistant: messages[i + 1].content });
    }
  }
  return turns.slice(-MAX_MEMORY_TURNS);
}

export default function V2Page() {
  const [messages, setMessages] = useState<V2ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages(loadMessages());
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (hydrated) saveMessages(messages);
  }, [messages, hydrated]);

  function newChat() {
    window.sessionStorage.removeItem(SESSION_STORAGE_KEY);
    setMessages([]);
  }

  async function send(query: string) {
    if (!query.trim() || loading) return;
    const conversation_history = deriveConversationHistory(messages);
    setMessages((m) => [...m, { role: "user", content: query }]);
    setInput("");
    setLoading(true);
    try {
      const res = await fetch("/api/v2/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, conversation_history }),
      });
      const data: V2ChatResponse = await res.json();
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
      <Header />
      <div className="mb-2 flex items-center justify-between">
        <span className="rounded bg-novartis-blue/10 px-2 py-0.5 text-xs font-medium text-novartis-darkblue">
          V2 · Agent loop + short-term memory
        </span>
        <button
          onClick={newChat}
          className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-600 hover:bg-slate-50"
        >
          New chat
        </button>
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto rounded-xl bg-slate-100 p-4">
        {messages.length === 0 && (
          <p className="text-sm text-slate-500">Ask a question, or try one of the suggestions below.</p>
        )}

        {messages.map((m, i) => (
          <V2MessageBubble key={i} message={m} />
        ))}
        {loading && <ThinkingIndicator />}
        <div ref={scrollRef} />
      </div>

      <SuggestedQuestions questions={SAMPLE_QUESTIONS} hasMessages={messages.length > 0} onSelect={send} />

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(input);
        }}
        className="mt-3 flex gap-2"
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

      <Footer />
    </main>
  );
}
