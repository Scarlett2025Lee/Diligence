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

  // Index by (doc, question) so the cell lookup is O(1) per render. Avoids
  // an N*M scan on every parent state change.
  const lookup = useMemo(() => {
    const m = new Map<string, CellResult>();
    for (const r of results) m.set(cellKey(r.doc_id, r.question_id), r);
    return m;
  }, [results]);

  return (
    <>
      <div className="overflow-x-auto rounded-xl border border-zinc-200 bg-white shadow-sm">
        <table className="min-w-full border-collapse">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 border-b border-zinc-200 bg-zinc-50 px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-zinc-500">
                Filing
              </th>
              {questions.map((q) => (
                <th
                  key={q.id}
                  className="min-w-[300px] border-b border-l border-zinc-200 bg-zinc-50 px-4 py-3 text-left text-xs font-medium text-zinc-600"
                >
                  {q.text}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filings.map((f) => (
              <tr key={f.doc_id} className="border-b border-zinc-100 last:border-0">
                <td className="sticky left-0 z-10 border-r border-zinc-200 bg-white px-4 py-4 align-top text-sm">
                  <div className="font-semibold tracking-tight">{f.ticker}</div>
                  <div className="text-xs text-zinc-500">
                    {f.form} · {f.filing_date}
                  </div>
                </td>
                {questions.map((q) => (
                  <td
                    key={q.id}
                    className="border-l border-zinc-100 px-4 py-4 align-top text-sm"
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
