"use client";

import type { Citation } from "@/lib/types";

type Props = {
  citation: Citation;
  onClick: (c: Citation) => void;
};

export function CitationChip({ citation, onClick }: Props) {
  return (
    <button
      type="button"
      onClick={() => onClick(citation)}
      className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-medium text-blue-300 ring-1 ring-inset ring-blue-400/30 transition hover:bg-blue-500/20 hover:text-blue-200 hover:ring-blue-400/60 hover:shadow-[0_0_12px_rgba(59,130,246,0.25)]"
      title={citation.section_title}
    >
      <span>Item {citation.item}</span>
      <span className="text-blue-400/70">↗</span>
    </button>
  );
}
