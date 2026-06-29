"use client";

import { useMemo, useState } from "react";

import { CellAnswer } from "./CellAnswer";
import { CitationDrawer } from "./CitationDrawer";
import { cellKey } from "@/lib/types";
import type { CellResult, Citation, Filing, Question } from "@/lib/types";

type Props = {
  filings: Filing[];
  questions: Question[];
  results: CellResult[];
};

export function MatrixGrid({ filings, questions, results }: Props) {
  const [openCitation, setOpenCitation] = useState<Citation | null>(null);

  const lookup = useMemo(() => {
    const m = new Map<string, CellResult>();
    for (const r of results) m.set(cellKey(r.doc_id, r.question_id), r);
    return m;
  }, [results]);

  return (
    <>
      <div className="overflow-x-auto rounded-2xl border border-white/10 bg-zinc-900/40 shadow-[0_20px_60px_-20px_rgba(0,0,0,0.6)] backdrop-blur">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-white/10 bg-zinc-950/80 px-5 py-3.5 text-left text-[10px] font-medium uppercase tracking-[0.18em] text-zinc-400 backdrop-blur">
                Filing
              </th>
              {questions.map((q) => (
                <th
                  key={q.id}
                  className="min-w-[320px] border-b border-l border-white/10 bg-zinc-900/40 px-5 py-3.5 text-left text-xs font-medium text-zinc-300 backdrop-blur"
                >
                  {q.text}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filings.map((f, rowIdx) => (
              <tr
                key={f.doc_id}
                className={`border-b border-white/5 last:border-0 ${
                  rowIdx % 2 === 1 ? "bg-white/[0.015]" : ""
                }`}
              >
                <td className="sticky left-0 z-10 border-r border-white/10 bg-zinc-950/80 px-5 py-5 align-top text-sm backdrop-blur">
                  <div className="font-semibold tracking-tight text-zinc-100">
                    {f.ticker}
                  </div>
                  <div className="mt-0.5 text-[11px] text-zinc-500">
                    {f.form} · {f.filing_date}
                  </div>
                </td>
                {questions.map((q) => (
                  <td
                    key={q.id}
                    className="border-l border-white/5 px-5 py-5 align-top text-sm"
                  >
                    <CellAnswer
                      result={lookup.get(cellKey(f.doc_id, q.id))}
                      onCitationClick={setOpenCitation}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <CitationDrawer
        citation={openCitation}
        onClose={() => setOpenCitation(null)}
      />
    </>
  );
}
