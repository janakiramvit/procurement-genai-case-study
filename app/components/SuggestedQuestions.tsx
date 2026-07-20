"use client";

interface SuggestedQuestionsProps {
  questions: string[];
  hasMessages: boolean;
  onSelect: (question: string) => void;
}

// Persistent chip row, shown above the input for the whole conversation (not just the
// empty state). Mobile: horizontal scroll, single row. sm+: wraps, capped at ~2 rows
// with vertical scroll as a fallback if it ever needs more.
export function SuggestedQuestions({ questions, hasMessages, onSelect }: SuggestedQuestionsProps) {
  return (
    <div className="mt-3">
      <p className="mb-1.5 text-xs font-medium text-slate-500">
        {hasMessages ? "Try another question" : "Try one of these"}
      </p>
      <div className="flex flex-nowrap gap-2 overflow-x-auto pb-1 sm:max-h-20 sm:flex-wrap sm:overflow-y-auto sm:overflow-x-visible">
        {questions.map((q) => (
          <button
            key={q}
            onClick={() => onSelect(q)}
            className="shrink-0 whitespace-nowrap rounded-full border border-novartis-blue/30 bg-white px-3 py-1.5 text-xs text-novartis-darkblue hover:bg-novartis-blue/5 sm:shrink sm:whitespace-normal"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
