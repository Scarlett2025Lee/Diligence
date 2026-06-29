"use client";

import { CitationChip } from "./CitationChip";
import type { CellResult, Citation } from "@/lib/types";

type Props = {
  result: CellResult | undefined;
  onCitationClick: (c: Citation) => void;
};

export function CellAnswer({ result, onCitationClick }: Props) {
  if (!result) {
    return <span className="text-zinc-700">—</span>;
  }
  if (result.status === "pending" || result.status === "running") {
    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2 text-xs text-blue-300/80">
          <span className="relative inline-flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-60" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-400" />
          </span>
          Thinking…
        </div>
        <div className="shimmer h-2 w-3/4 rounded" />
        <div className="shimmer h-2 w-1/2 rounded" />
      </div>
    );
  }
  if (result.status === "error") {
    return (
      <span className="rounded-md bg-red-500/10 px-2 py-1 text-xs text-red-300 ring-1 ring-inset ring-red-500/30">
        Failed to answer
      </span>
    );
  }
  return (
    <div className="space-y-2.5">
      <p className="leading-relaxed text-zinc-100">{result.answer}</p>
      {result.citations.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {result.citations.map((c, i) => (
            <CitationChip
              key={`${c.chunk_id}-${i}`}
              citation={c}
              onClick={onCitationClick}
            />
          ))}
        </div>
      )}
      <div className="flex gap-3 text-[10px] uppercase tracking-[0.15em] text-zinc-500">
        <span>${result.cost_usd.toFixed(4)}</span>
        <span>{result.latency_ms} ms</span>
      </div>
    </div>
  );
}
