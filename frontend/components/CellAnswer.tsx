"use client";

import { CitationChip } from "./CitationChip";
import type { CellResult, Citation } from "@/lib/types";

type Props = {
  result: CellResult | undefined;
  onCitationClick: (c: Citation) => void;
};

export function CellAnswer({ result, onCitationClick }: Props) {
  if (!result) {
    return <span className="text-zinc-300">—</span>;
  }
  if (result.status === "pending" || result.status === "running") {
    return (
      <div className="flex items-center gap-2 text-xs text-zinc-400">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-zinc-300" />
        Thinking…
      </div>
    );
  }
  if (result.status === "error") {
    return <span className="text-xs text-red-500">Failed to answer</span>;
  }
  return (
    <div className="space-y-2">
      <p className="leading-relaxed text-zinc-900">{result.answer}</p>
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
      <div className="flex gap-3 text-[10px] uppercase tracking-wide text-zinc-400">
        <span>${result.cost_usd.toFixed(4)}</span>
        <span>{result.latency_ms} ms</span>
      </div>
    </div>
  );
}
