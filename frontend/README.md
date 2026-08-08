# Diligence frontend

Next.js 14 + Tailwind. Renders the matrix grid UI: rows = filings, columns =
questions, each cell shows the agent's answer + clickable citation chips.

## Run it

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000.

## Backend wiring

The dev server proxies `/api/*` to the FastAPI backend. Default target is
`http://localhost:8000`; override with `NEXT_PUBLIC_BACKEND_URL` in
`.env.local` if you run the backend elsewhere.

Until `/api/matrix` exists, the home page renders against `lib/mock.ts`.
Swap to the live client by replacing the mock import in `app/page.tsx`
with a server-side `runMatrix()` call (see `lib/api.ts`).
