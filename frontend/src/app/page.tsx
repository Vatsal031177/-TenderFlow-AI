"use client";

import { useEffect, useState } from "react";

interface GraphDependency {
  target: string;
  relation: string;
  note: string;
}

interface QuoteItem {
  id: number;
  position_no: string;
  requested_description: string;
  quantity: number;
  unit: string;
  matched_sku: string | null;
  matched_name: string | null;
  unit_price: number;
  line_total: number;
  margin_pct: number;
  confidence: number;
  retrieval_source: string;
  graph_dependencies: GraphDependency[];
  needs_review: boolean;
}

interface Tender {
  id: number;
  title: string;
  customer_name: string;
  total_net: number;
  estimated_margin_pct: number;
  status: string;
  guardrail_alerts: string[];
  trace_id: string | null;
  items: QuoteItem[];
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const SAMPLE_LV = `Pos 1.1: Fire-rated drywall gypsum board F90 DIN 4102-4 12.5mm 240 m2
Pos 1.2: Rockwool mineral wool thermal insulation 100mm WLG 035 240 m2
Pos 2.1: Structural ready-mix concrete C30/37 XC4 for floor slab 85 m3`;

export default function WorkbenchPage() {
  const [title, setTitle] = useState("Munich Office Retrofit - Lot 04 Interior");
  const [customerName, setCustomerName] = useState("Bavaria Bau GmbH");
  const [rawText, setRawText] = useState(SAMPLE_LV);
  const [loading, setLoading] = useState(false);
  const [activeTender, setActiveTender] = useState<Tender | null>(null);
  const [history, setHistory] = useState<Tender[]>([]);
  const [error, setError] = useState<string | null>(null);

  async function fetchTenders() {
    try {
      const res = await fetch(`${API_URL}/api/tenders`);
      if (res.ok) {
        const data: Tender[] = await res.json();
        setHistory(data);
        if (!activeTender && data.length > 0) setActiveTender(data[0]);
      }
    } catch {
      // Backend may still be booting
    }
  }

  useEffect(() => {
    fetchTenders();
  }, []);

  async function handleRunAgent(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/tenders/process`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title, customer_name: customerName, raw_text: rawText }),
      });
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const tender: Tender = await res.json();
      setActiveTender(tender);
      setHistory((prev) => [tender, ...prev]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to process tender");
    } finally {
      setLoading(false);
    }
  }

  async function handleApprovePrice(tenderId: number, item: QuoteItem) {
    const updated = window.prompt(`Adjust unit price for ${item.matched_sku || item.position_no}:`, String(item.unit_price));
    if (!updated) return;
    const price = parseFloat(updated);
    if (Number.isNaN(price)) return;

    const res = await fetch(`${API_URL}/api/tenders/${tenderId}/items/${item.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ unit_price: price }),
    });
    if (res.ok) {
      const tender: Tender = await res.json();
      setActiveTender(tender);
      setHistory((prev) => prev.map((t) => (t.id === tender.id ? tender : t)));
    }
  }

  return (
    <main className="min-h-screen p-6 max-w-7xl mx-auto space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white">
            TenderFlow AI <span className="text-emerald-400 text-sm font-mono ml-2">v1.0 • Agentic Quoting</span>
          </h1>
          <p className="text-slate-400 text-sm">
            BoQ Extraction → Hybrid RAG (Elasticsearch + pgvector) → Graph RAG Norms → Margin Guardrails
          </p>
        </div>
        {activeTender?.trace_id && (
          <span className="px-3 py-1 rounded-full bg-slate-900 border border-slate-700 text-xs font-mono text-sky-400">
            LangSmith Trace: {activeTender.trace_id}
          </span>
        )}
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Tender Ingestion */}
        <section className="lg:col-span-4 bg-slate-900/70 border border-slate-800 rounded-xl p-5 space-y-4">
          <h2 className="text-lg font-semibold">1. Ingest Tender / BoQ</h2>
          <form onSubmit={handleRunAgent} className="space-y-3">
            <div>
              <label className="block text-xs text-slate-400 mb-1">Project Title</label>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Customer</label>
              <input
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm"
                required
              />
            </div>
            <div>
              <label className="block text-xs text-slate-400 mb-1">Raw BoQ / Leistungsverzeichnis</label>
              <textarea
                rows={7}
                value={rawText}
                onChange={(e) => setRawText(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs font-mono"
                required
              />
            </div>
            {error && <p className="text-xs text-rose-400">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full bg-emerald-500 hover:bg-emerald-400 disabled:opacity-50 text-slate-950 font-semibold py-2.5 rounded-lg text-sm transition"
            >
              {loading ? "Running Agent Pipeline..." : "Generate AI Quote"}
            </button>
          </form>

          {history.length > 0 && (
            <div className="pt-4 border-t border-slate-800">
              <h3 className="text-xs uppercase tracking-wider text-slate-400 mb-2">Recent Quotes</h3>
              <ul className="space-y-2 max-h-48 overflow-y-auto">
                {history.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => setActiveTender(t)}
                      className={`w-full text-left px-3 py-2 rounded-lg text-xs border transition ${
                        activeTender?.id === t.id
                          ? "bg-slate-800 border-emerald-500/60"
                          : "bg-slate-950 border-slate-800 hover:border-slate-700"
                      }`}
                    >
                      <div className="font-medium text-slate-200 truncate">{t.title}</div>
                      <div className="text-slate-400 flex justify-between mt-0.5">
                        <span>€{t.total_net.toLocaleString()}</span>
                        <span>{t.status}</span>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {/* Right: Structured Quote & Guardrails */}
        <section className="lg:col-span-8 space-y-4">
          {!activeTender ? (
            <div className="bg-slate-900/50 border border-dashed border-slate-800 rounded-xl p-12 text-center text-slate-400">
              Submit a tender BoQ on the left to trigger the Hybrid + Graph RAG quoting agent.
            </div>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Total Net Quote</div>
                  <div className="text-2xl font-bold text-white mt-1">
                    €{activeTender.total_net.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                  </div>
                </div>
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Estimated Margin</div>
                  <div className="text-2xl font-bold text-emerald-400 mt-1">
                    {activeTender.estimated_margin_pct}%
                  </div>
                </div>
                <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
                  <div className="text-xs text-slate-400">Pipeline Status</div>
                  <div className="mt-1">
                    <span
                      className={`inline-block px-2.5 py-1 rounded-md text-xs font-semibold ${
                        activeTender.status === "READY_TO_SEND"
                          ? "bg-emerald-500/20 text-emerald-300"
                          : "bg-amber-500/20 text-amber-300"
                      }`}
                    >
                      {activeTender.status}
                    </span>
                  </div>
                </div>
              </div>

              {activeTender.guardrail_alerts.length > 0 && (
                <div className="bg-amber-950/40 border border-amber-700/60 rounded-xl p-4 space-y-1.5">
                  <div className="text-xs font-semibold uppercase tracking-wider text-amber-300">
                    Guardrail & Graph RAG Alerts ({activeTender.guardrail_alerts.length})
                  </div>
                  <ul className="text-xs text-amber-100 list-disc pl-4 space-y-1">
                    {activeTender.guardrail_alerts.map((alert, i) => (
                      <li key={i}>{alert}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="p-3">Pos</th>
                        <th className="p-3">BoQ Request & Matched SKU</th>
                        <th className="p-3">Qty</th>
                        <th className="p-3">Unit €</th>
                        <th className="p-3">Total €</th>
                        <th className="p-3">Confidence</th>
                        <th className="p-3">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {activeTender.items.map((item) => (
                        <tr key={item.id} className={item.needs_review ? "bg-amber-950/15" : ""}>
                          <td className="p-3 font-mono text-slate-300">{item.position_no}</td>
                          <td className="p-3 space-y-1">
                            <div className="text-slate-200">{item.requested_description}</div>
                            <div className="text-emerald-400 font-mono">
                              {item.matched_sku ? `${item.matched_sku} — ${item.matched_name}` : "UNMATCHED"}
                            </div>
                            {item.graph_dependencies.length > 0 && (
                              <div className="flex flex-wrap gap-1 pt-1">
                                {item.graph_dependencies.map((dep, idx) => (
                                  <span
                                    key={idx}
                                    title={dep.note}
                                    className="px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 text-[10px]"
                                  >
                                    {dep.relation}: {dep.target}
                                  </span>
                                ))}
                              </div>
                            )}
                          </td>
                          <td className="p-3 whitespace-nowrap">
                            {item.quantity} {item.unit}
                          </td>
                          <td className="p-3 font-mono">€{item.unit_price.toFixed(2)}</td>
                          <td className="p-3 font-mono font-semibold">€{item.line_total.toFixed(2)}</td>
                          <td className="p-3">
                            <span className="font-mono">{(item.confidence * 100).toFixed(0)}%</span>
                            <div className="text-[10px] text-slate-500">{item.retrieval_source}</div>
                          </td>
                          <td className="p-3">
                            <button
                              onClick={() => handleApprovePrice(activeTender.id, item)}
                              className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-200"
                            >
                              Adjust
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
