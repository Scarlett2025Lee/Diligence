"use client";

import { useEffect, useState } from "react";

import { MatrixGrid } from "./MatrixGrid";
import { listFilings, runMatrix } from "@/lib/api";
import type { CellResult, Filing, Question } from "@/lib/types";

type Status = "idle" | "loading-filings" | "ready" | "running" | "done" | "error";

type Props = {
  initialQuestions: Question[];
};

/** Live-data wrapper around <MatrixGrid />. Loads filings on mount,
 * runs the matrix on demand, and re-renders the grid as cells arrive. */
export function Matrix({ initialQuestions }: Props) {
  const [filings, setFilings] = useState<Filing[]>([]);
  const [questions] = useState<Question[]>(initialQuestions);
  const [results, setResults] = useState<CellResult[]>([]);
  const [status, setStatus] = useState<Status>("loading-filings");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listFilings()
      .then((rows) => {
        if (cancelled) return;
        setFilings(rows);
        setStatus(rows.length > 0 ? "ready" : "idle");
      })
      .catch((e) => {
        if (cancelled) return;
        setError(`Failed to load filings: ${e.message}`);
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleRun() {
    if (filings.length === 0 || questions.length === 0) return;
    setStatus("running");
    setError(null);
    // Seed every cell as "running" so the user sees the whole grid
    // light up while the backend works.
    setResults(
      filings.flatMap((f) =>
        questions.map((q) => ({
          doc_id: f.doc_id,
          question_id: q.id,
          status: "running" as const,
          answer: null,
          citations: [],
          cost_usd: 0,
          latency_ms: 0,
        })),
      ),
    );
    try {
      const finished = await runMatrix(filings, questions);
      setResults(finished);
      setStatus("done");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(`Run failed: ${msg}`);
      setStatus("error");
    }
  }

  if (status === "loading-filings") {
    return <Placeholder>Loading filings…</Placeholder>;
  }
  if (status === "idle" && filings.length === 0) {
    return (
      <Placeholder>
        No filings ingested yet. Run{" "}
        <code className="rounded bg-zinc-100 px-1 py-0.5">
          python -m scripts.ingest --tickers AAPL --forms 10-K
        </code>{" "}
        first.
      </Placeholder>
    );
  }

  return (
    <>
      <div className="mb-4 flex items-center gap-3">
        <button
          type="button"
          onClick={handleRun}
          disabled={status === "running"}
          className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:bg-zinc-300"
        >
          {status === "running" ? "Running…" : "Run matrix"}
        </button>
        <span className="text-xs text-zinc-500">
          {filings.length} filings · {questions.length} questions ·{" "}
          {filings.length * questions.length} cells
        </span>
        {error && <span className="text-xs text-red-600">{error}</span>}
      </div>

      <MatrixGrid filings={filings} questions={questions} results={results} />
    </>
  );
}


function Placeholder({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-zinc-300 bg-white px-6 py-12 text-center text-sm text-zinc-500">
      {children}
    </div>
  );
}
