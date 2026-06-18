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
      className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-xs text-blue-700 transition hover:bg-blue-100"
      title={citation.section_title}
    >
      <span className="font-medium">Item {citation.item}</span>
      <span className="text-blue-500/70">↗</span>
    </button>
  );
}
