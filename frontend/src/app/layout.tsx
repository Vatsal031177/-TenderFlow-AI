import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TenderFlow AI | Construction Tendering Workbench",
  description: "Agentic BoQ Extraction, Hybrid + Graph RAG Matching & Quoting Guardrails",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-slate-950 text-slate-100 antialiased">{children}</body>
    </html>
  );
}
