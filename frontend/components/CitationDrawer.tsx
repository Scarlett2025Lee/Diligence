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
        className="fixed inset-0 z-40 bg-zinc-900/20"
        onClick={onClose}
        aria-hidden
      />
      <aside className="fixed inset-y-0 right-0 z-50 flex w-full max-w-xl flex-col border-l border-zinc-200 bg-white shadow-xl">
        <header className="flex items-start justify-between border-b border-zinc-200 px-6 py-4">
          <div>
            <div className="text-xs uppercase tracking-wide text-zinc-500">
              Item {citation.item} · {citation.section_title}
            </div>
            <div className="mt-0.5 text-sm font-medium text-zinc-700">
              {citation.doc_id}
            </div>
            <div className="text-xs text-zinc-400">
              chars {citation.body_start}–{citation.body_end} of section body
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-zinc-400 transition hover:bg-zinc-100 hover:text-zinc-700"
            aria-label="Close"
          >
            ✕
          </button>
        </header>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <div className="flex items-center justify-between">
            <div className="text-xs font-medium uppercase tracking-wide text-zinc-400">
              Quoted passage
            </div>
            {citation.source_url && (
              <a
                href={citation.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 rounded-md border border-zinc-200 px-2 py-1 text-xs text-zinc-700 transition hover:border-blue-300 hover:bg-blue-50 hover:text-blue-700"
              >
                View on EDGAR <span aria-hidden>↗</span>
              </a>
            )}
          </div>
          <blockquote className="mt-2 whitespace-pre-wrap border-l-2 border-blue-300 bg-blue-50/40 px-4 py-3 text-sm leading-relaxed text-zinc-800">
            {citation.quote}
          </blockquote>
          {citation.source_url && (
            <p className="mt-3 text-xs text-zinc-500">
              The cleaned excerpt above is what the agent reads. Open the original
              on EDGAR to see full formatting — tables, footnotes, and inline XBRL.
            </p>
          )}
        </div>
      </aside>
    </>
  );
}
