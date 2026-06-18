import { MatrixGrid } from "@/components/MatrixGrid";
import { mockFilings, mockQuestions, mockResults } from "@/lib/mock";

export default function Home() {
  return (
    <main className="min-h-screen px-6 py-10 md:px-10">
      <header className="mb-8 max-w-3xl">
        <div className="text-xs font-medium uppercase tracking-widest text-blue-600">
          Diligence
        </div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-zinc-900">
          Finance Matrix Agent
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-zinc-600">
          Ask structured questions across many SEC filings at once. Each cell is an
          agent that answers a question against a single document and returns a
          citation. Click a citation chip to see the exact passage it pulled from.
        </p>
      </header>

      <MatrixGrid
        filings={mockFilings}
        questions={mockQuestions}
        results={mockResults}
      />

      <footer className="mt-8 text-xs text-zinc-400">
        Showing mock data. Wire up <code className="rounded bg-zinc-100 px-1 py-0.5 text-[11px]">/api/matrix</code>{" "}
        to replace with live answers.
      </footer>
    </main>
  );
}
