import type { Citation } from "../types";

// Original KnowledgeBase files are served statically from public/sources/ (copied
// verbatim from data/KnowledgeBase/ at build time) so citations can link straight to
// the source document. This is UI-only: it reuses the citation metadata the RAG
// agent already returns (source, location) and does not touch retrieval.
function sourceFileUrl(source: string): string {
  return `/sources/${encodeURIComponent(source)}`;
}

function formatLocation(location: string): string {
  return location.charAt(0).toUpperCase() + location.slice(1);
}

export function EvidenceSection({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;

  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 text-xs">
      <div className="border-b border-slate-200 px-3 py-2 font-medium text-slate-600">Evidence</div>
      <ul className="divide-y divide-slate-200">
        {citations.map((c) => (
          <li key={c.marker} className="flex items-center justify-between gap-3 px-3 py-2">
            <span className="min-w-0 text-slate-600">
              <span className="mr-1">📄</span>
              <span className="font-medium text-slate-700">{c.source}</span>
              <span className="text-slate-400"> — Location: {formatLocation(c.location)}</span>
            </span>
            <a
              href={sourceFileUrl(c.source)}
              target="_blank"
              rel="noopener noreferrer"
              className="shrink-0 rounded-full border border-novartis-blue/30 px-2.5 py-1 text-novartis-darkblue hover:bg-novartis-blue/5"
            >
              Open ↗
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
