import { Matrix } from "@/components/Matrix";
import { mockQuestions } from "@/lib/mock";

export default function Home() {
  return (
    <main className="min-h-screen px-6 py-12 md:px-10">
      <header className="mb-10 max-w-3xl">
        <div className="text-xs font-medium uppercase tracking-[0.2em] text-blue-400/90">
          Diligence
        </div>
        <h1 className="mt-2 bg-gradient-to-br from-white via-zinc-100 to-zinc-400 bg-clip-text text-4xl font-semibold tracking-tight text-transparent">
          Finance Matrix Agent
        </h1>
        <p className="mt-3 text-sm leading-relaxed text-zinc-400">
          Ask structured questions across many SEC filings at once. Each cell is an
          agent that answers a question against a single document and returns a
          citation. Click a citation chip to see the exact passage it pulled from.
        </p>
      </header>

      <Matrix initialQuestions={mockQuestions} />
    </main>
  );
}
