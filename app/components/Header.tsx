"use client";

import { useEffect, useRef, useState } from "react";

// Logo lives at public/novartis-logo.png. If it's ever missing, the <img> is hidden so
// the header still renders cleanly with text only.
//
// A same-origin 404 often resolves faster than React hydration attaches the onError
// listener (native <img> error events don't bubble, so React attaches them directly to
// the node during commit -- if the request already failed before that, the event is
// missed). The mount-time complete/naturalWidth check below covers that already-failed
// case; onError stays as a fallback for a later/slower failure.
export function Header() {
  const [logoFailed, setLogoFailed] = useState(false);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth === 0) {
      setLogoFailed(true);
    }
  }, []);

  return (
    <header className="mb-4 flex items-center gap-3 border-b border-slate-200 pb-3">
      {!logoFailed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          ref={imgRef}
          src="/novartis-logo.png"
          alt="Novartis"
          className="h-10 w-auto shrink-0 object-contain"
          onError={() => setLogoFailed(true)}
        />
      )}
      <div className="flex min-w-0 flex-col leading-tight">
        <span className="truncate text-lg font-semibold text-novartis-darkblue">Procurement AI Helpdesk</span>
        <span className="text-xs text-slate-500">Enterprise AI Prototype · Case Study Submission</span>
      </div>
    </header>
  );
}
