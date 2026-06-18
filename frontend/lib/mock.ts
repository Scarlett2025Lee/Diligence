// Mock data so the UI can be developed (and screenshotted) before the
// backend grid endpoint exists. Real answers will replace this once the
// /api/matrix endpoint lands. Citations point at plausible Item ranges
// so the citation-drawer UX can be exercised end-to-end.

import type { CellResult, Filing, Question } from "./types";

export const mockFilings: Filing[] = [
  { doc_id: "0000320193-24-000123", ticker: "AAPL",  form: "10-K", filing_date: "2024-11-01" },
  { doc_id: "0000789019-24-000041", ticker: "MSFT",  form: "10-K", filing_date: "2024-07-30" },
  { doc_id: "0001652044-24-000022", ticker: "GOOGL", form: "10-K", filing_date: "2024-01-30" },
];

export const mockQuestions: Question[] = [
  { id: "q-revenue",    text: "What was total revenue and YoY growth?" },
  { id: "q-segment",    text: "Which segment grew the fastest?" },
  { id: "q-risk-top",   text: "What is the most prominent risk factor?" },
  { id: "q-ai-mention", text: "How is AI discussed in MD&A?" },
];

export const mockResults: CellResult[] = [
  {
    doc_id: "0000320193-24-000123",
    question_id: "q-revenue",
    status: "done",
    answer:
      "Total net sales were $391.0B for fiscal 2024, up 2% year over year, driven by Services growth offsetting flat iPhone revenue.",
    citations: [
      {
        chunk_id: 142, doc_id: "0000320193-24-000123", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 1200, body_end: 1880,
        quote:
          "Total net sales increased 2% or $8.0 billion during 2024 compared to 2023, primarily due to higher net sales of Services...",
      },
    ],
    cost_usd: 0.0021, latency_ms: 1840,
  },
  {
    doc_id: "0000320193-24-000123",
    question_id: "q-segment",
    status: "done",
    answer: "Services was the fastest-growing segment at +13% YoY, reaching $96.2B.",
    citations: [
      {
        chunk_id: 158, doc_id: "0000320193-24-000123", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 4400, body_end: 4920,
        quote: "Services net sales increased 13% or $11.1 billion during 2024 compared to 2023...",
      },
    ],
    cost_usd: 0.0019, latency_ms: 1720,
  },
  {
    doc_id: "0000320193-24-000123",
    question_id: "q-risk-top",
    status: "done",
    answer:
      "Concentration of supply and manufacturing in China — disruption from geopolitical tension or natural disasters could materially harm operations.",
    citations: [
      {
        chunk_id: 41, doc_id: "0000320193-24-000123", item: "1A",
        section_title: "Risk Factors",
        body_start: 0, body_end: 720,
        quote:
          "The Company's manufacturing partners' operations are concentrated in a limited number of geographic locations...",
      },
    ],
    cost_usd: 0.0024, latency_ms: 2010,
  },
  {
    doc_id: "0000320193-24-000123",
    question_id: "q-ai-mention",
    status: "done",
    answer:
      "Apple discusses Apple Intelligence as a key investment area in fiscal 2024, with related R&D spend included in the 9% YoY increase in operating expenses.",
    citations: [
      {
        chunk_id: 201, doc_id: "0000320193-24-000123", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 8200, body_end: 8800,
        quote: "Research and development expense for 2024 increased 9% compared to 2023, driven by higher headcount and ongoing investments in Apple Intelligence...",
      },
    ],
    cost_usd: 0.0027, latency_ms: 2240,
  },

  {
    doc_id: "0000789019-24-000041",
    question_id: "q-revenue",
    status: "done",
    answer: "Microsoft reported total revenue of $245.1B in fiscal 2024, up 16% YoY.",
    citations: [
      {
        chunk_id: 312, doc_id: "0000789019-24-000041", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 200, body_end: 740,
        quote: "Revenue increased $33.2 billion or 16% driven by growth across each of our segments...",
      },
    ],
    cost_usd: 0.0020, latency_ms: 1790,
  },
  {
    doc_id: "0000789019-24-000041",
    question_id: "q-segment",
    status: "done",
    answer: "Intelligent Cloud led growth at +20% YoY, propelled by Azure and AI services.",
    citations: [
      {
        chunk_id: 318, doc_id: "0000789019-24-000041", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 1500, body_end: 2020,
        quote: "Intelligent Cloud revenue increased 20%, driven by Azure and other cloud services...",
      },
    ],
    cost_usd: 0.0018, latency_ms: 1680,
  },
  {
    doc_id: "0000789019-24-000041",
    question_id: "q-risk-top",
    status: "running",
    answer: null, citations: [], cost_usd: 0, latency_ms: 0,
  },
  {
    doc_id: "0000789019-24-000041",
    question_id: "q-ai-mention",
    status: "done",
    answer:
      "AI is positioned as the central strategic narrative — copilot products, OpenAI partnership, and Azure AI infrastructure are repeatedly cited as growth drivers.",
    citations: [
      {
        chunk_id: 340, doc_id: "0000789019-24-000041", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 5200, body_end: 5780,
        quote: "We continue to invest significantly in our cloud and AI infrastructure...",
      },
    ],
    cost_usd: 0.0029, latency_ms: 2380,
  },

  {
    doc_id: "0001652044-24-000022",
    question_id: "q-revenue",
    status: "done",
    answer: "Alphabet reported $307.4B in revenue for fiscal 2023, up 9% YoY.",
    citations: [
      {
        chunk_id: 502, doc_id: "0001652044-24-000022", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 300, body_end: 820,
        quote: "Revenues were $307.4 billion, an increase of 9%, with constant currency revenue growth of 10%...",
      },
    ],
    cost_usd: 0.0022, latency_ms: 1880,
  },
  {
    doc_id: "0001652044-24-000022",
    question_id: "q-segment",
    status: "done",
    answer: "Google Cloud grew fastest at +26% YoY, reaching $33.1B.",
    citations: [
      {
        chunk_id: 511, doc_id: "0001652044-24-000022", item: "7",
        section_title: "Management's Discussion and Analysis",
        body_start: 2400, body_end: 2900,
        quote: "Google Cloud revenues increased $7.0 billion to $33.1 billion, representing growth of 26%...",
      },
    ],
    cost_usd: 0.0019, latency_ms: 1700,
  },
  {
    doc_id: "0001652044-24-000022",
    question_id: "q-risk-top",
    status: "done",
    answer:
      "Ongoing regulatory and antitrust scrutiny across the U.S. and EU — adverse outcomes could force structural changes to advertising, search, or Android.",
    citations: [
      {
        chunk_id: 78, doc_id: "0001652044-24-000022", item: "1A",
        section_title: "Risk Factors",
        body_start: 1100, body_end: 1700,
        quote:
          "We are subject to a wide variety of complex and changing U.S. and foreign laws... including ongoing investigations and litigation...",
      },
    ],
    cost_usd: 0.0023, latency_ms: 1960,
  },
  {
    doc_id: "0001652044-24-000022",
    question_id: "q-ai-mention",
    status: "error",
    answer: null, citations: [], cost_usd: 0, latency_ms: 0,
  },
];
