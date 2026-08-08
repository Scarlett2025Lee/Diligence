// API contract between the FastAPI backend and the Next.js frontend.
// Keep these aligned with the Pydantic models in src/api/. When the backend
// adds a field, mirror it here; the type-check step will surface any drift.

export type Filing = {
  doc_id: string;       // EDGAR accession number
  ticker: string;
  form: "10-K" | "10-Q";
  filing_date: string;  // ISO date
};

export type Question = {
  id: string;
  text: string;
};

export type Citation = {
  chunk_id: number;
  doc_id: string;
  item: string;           // 10-K item id, e.g. "1A"
  section_title: string;
  body_start: number;     // offset into the cited Section's body
  body_end: number;
  quote: string;          // exact text supporting the answer
  // Resolved by the backend (computed from the documents table) — links
  // to the original filing on EDGAR with full HTML formatting.
  source_url?: string | null;
};

export type CellStatus = "pending" | "running" | "done" | "error";

export type CellResult = {
  doc_id: string;
  question_id: string;
  status: CellStatus;
  answer: string | null;
  citations: Citation[];
  cost_usd: number;
  latency_ms: number;
};

// Key used by MatrixGrid to look up a cell from (doc, question).
export const cellKey = (docId: string, questionId: string) =>
  `${docId}::${questionId}`;
