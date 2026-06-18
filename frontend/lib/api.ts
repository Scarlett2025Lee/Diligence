// Typed client for the FastAPI backend. Endpoints are stubs until the
// backend lands; `runMatrix` is implemented because the grid page needs
// to be able to swap from mock data to real fetches with one import flip.

import type { CellResult, Filing, Question } from "./types";

const headers = { "Content-Type": "application/json" } as const;

export async function listFilings(): Promise<Filing[]> {
  const res = await fetch("/api/filings");
  if (!res.ok) throw new Error(`listFilings ${res.status}`);
  return res.json();
}

export async function runMatrix(
  filings: Filing[],
  questions: Question[],
): Promise<CellResult[]> {
  const res = await fetch("/api/matrix", {
    method: "POST",
    headers,
    body: JSON.stringify({
      doc_ids: filings.map((f) => f.doc_id),
      questions: questions.map((q) => ({ id: q.id, text: q.text })),
    }),
  });
  if (!res.ok) throw new Error(`runMatrix ${res.status}`);
  return res.json();
}
