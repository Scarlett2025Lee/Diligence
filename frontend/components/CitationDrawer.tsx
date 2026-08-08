"use client";

import type { Citation } from "@/lib/types";

type Props = {
  citation: Citation | null;
  onClose: () => void;
};

export function CitationDrawer({ citation, onClose }: Props) {
  if (!citation) return null;
  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-zinc-950/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden
      />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-white/10 bg-zinc-900/85 shadow-2xl backdrop-blur-xl">
        <header className="flex items-start justify-between border-b border-white/10 px-6 py-5">
          <div>
            <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-blue-300/80">
              Item {citation.item} · {citation.section_title}
            </div>
            <div className="mt-1 font-mono text-sm text-zinc-200">
              {citation.doc_id}
            </div>
            <div className="text-[11px] text-zinc-500">
              chars {citation.body_start}–{citation.body_end} of section body
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-zinc-400 transition hover:bg-white/5 hover:text-zinc-100"
            aria-label="Close"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-500">
              Quoted passage
            </div>
            {citation.source_url && (
              <a
                href={citation.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] text-zinc-300 transition hover:border-blue-400/40 hover:bg-blue-500/10 hover:text-blue-200"
              >
                View on EDGAR <span aria-hidden>↗</span>
              </a>
            )}
          </div>
          <blockquote className="mt-3 whitespace-pre-wrap rounded-md border border-white/5 bg-blue-500/5 px-4 py-3 text-sm leading-relaxed text-zinc-200 shadow-[inset_2px_0_0_rgba(96,165,250,0.55)]">
            {citation.quote}
          </blockquote>
          {citation.source_url && (
            <p className="mt-3 text-[11px] text-zinc-500">
              The cleaned excerpt above is what the agent reads. Open the original
              on EDGAR to see full formatting — tables, footnotes, and inline XBRL.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
