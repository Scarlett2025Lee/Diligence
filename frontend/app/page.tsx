import { Matrix } from "@/components/Matrix";
import { mockQuestions } from "@/lib/mock";

export default function Home() {
  // The questions list is a frontend authoring concern (Hebbia-style "what
  // do I want to ask across every filing"). Filings come from the backend.
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

      <Matrix initialQuestions={mockQuestions} />
    </main>
  );
}
