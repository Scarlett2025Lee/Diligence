import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"], display: "swap" });

export const metadata: Metadata = {
  title: "Diligence — Finance Matrix Agent",
  description:
    "Hebbia-style document intelligence over SEC filings. Ask structured questions across many documents at once; every answer cites its source.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={inter.className}>
      <body className="relative min-h-screen overflow-x-hidden bg-zinc-950 text-zinc-100 antialiased">
        {/* Ambient glow + scanlines: a thin atmospheric layer behind the
         * content. Both are pointer-events-none so they never intercept
         * clicks. */}
        <div className="pointer-events-none fixed inset-0 -z-10 bg-[radial-gradient(circle_at_top,_rgba(59,130,246,0.10),_transparent_55%)]" />
        <div className="pointer-events-none fixed inset-0 -z-10 scanlines" />
        {children}
      </body>
    </html>
  );
}
