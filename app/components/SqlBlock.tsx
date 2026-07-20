"use client";

import { useState } from "react";

export function SqlBlock({
  sql,
  columns,
  rows,
}: {
  sql: string;
  columns: string[];
  rows: Record<string, unknown>[];
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-2 rounded-lg border border-slate-200 text-xs">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full px-3 py-2 text-left font-medium text-slate-600 hover:text-slate-900"
      >
        {open ? "hide SQL ▲" : "show generated SQL ▼"}
      </button>
      {open && (
        <div className="space-y-2 border-t border-slate-200 p-3">
          <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-slate-900 p-2 text-slate-100">{sql}</pre>
          {rows.length > 0 && (
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse text-left">
                <thead>
                  <tr>
                    {columns.map((c) => (
                      <th key={c} className="border-b border-slate-300 px-2 py-1 font-semibold text-slate-600">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.slice(0, 10).map((r, i) => (
                    <tr key={i}>
                      {columns.map((c) => (
                        <td key={c} className="border-b border-slate-100 px-2 py-1 text-slate-500">
                          {String(r[c] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length > 10 && (
                <p className="mt-1 text-slate-400">showing 10 of {rows.length} rows</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
