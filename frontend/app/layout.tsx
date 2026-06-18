import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Diligence — Finance Matrix Agent",
  description:
    "Hebbia-style document intelligence over SEC filings. Ask structured questions across many documents at once; every answer cites its source.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-zinc-50 text-zinc-900 antialiased">{children}</body>
    </html>
  );
}
