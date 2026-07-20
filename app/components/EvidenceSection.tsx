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

interface EvidenceSectionProps {
  citations: Citation[];
  variant?: "verified" | "unverified";
}

const VARIANT_STYLES = {
  verified: {
    wrap: "border-slate-200 bg-slate-50",
    header: "border-slate-200 text-slate-600",
    divide: "divide-slate-200",
    label: "text-slate-600",
    name: "text-slate-700",
    meta: "text-slate-400",
    link: "border-novartis-blue/30 text-novartis-darkblue hover:bg-novartis-blue/5",
    title: "Evidence",
    note: null as string | null,
  },
  unverified: {
    wrap: "border-amber-200 bg-amber-50",
    header: "border-amber-200 text-amber-700",
    divide: "divide-amber-200",
    label: "text-amber-800",
    name: "text-amber-900",
    meta: "text-amber-600",
    link: "border-amber-400/50 text-amber-800 hover:bg-amber-100",
    title: "⚠ Evidence (retrieved, not verified)",
    note: "These sources were retrieved but the generated answer from them didn't pass the groundedness check — inspect them yourself before relying on this.",
  },
};

export function EvidenceSection({ citations, variant = "verified" }: EvidenceSectionProps) {
  if (citations.length === 0) return null;
  const styles = VARIANT_STYLES[variant];

  return (
    <div className={`mt-2 rounded-lg border text-xs ${styles.wrap}`}>
      <div className={`border-b px-3 py-2 font-medium ${styles.header}`}>{styles.title}</div>
      {styles.note && <div className={`px-3 pb-2 pt-1 ${styles.label}`}>{styles.note}</div>}
      <ul className={`divide-y ${styles.divide}`}>
        {citations.map((c) => (
          <li key={c.marker} className="flex items-center justify-between gap-3 px-3 py-2">
            <span className={`min-w-0 ${styles.label}`}>
              <span className="mr-1">📄</span>
              <span className={`font-medium ${styles.name}`}>{c.source}</span>
              <span className={styles.meta}> — Location: {formatLocation(c.location)}</span>
            </span>
            <a
              href={sourceFileUrl(c.source)}
              target="_blank"
              rel="noopener noreferrer"
              className={`shrink-0 rounded-full border px-2.5 py-1 ${styles.link}`}
            >
              Open ↗
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
