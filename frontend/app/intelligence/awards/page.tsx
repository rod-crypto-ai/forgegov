"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { CompanyIdentity } from "@/components/company-identity";
import { Activity, BadgeDollarSign, Database, RefreshCw, Search, ShieldCheck, TriangleAlert } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Winner = { recipient_name: string; recipient_uei?: string; award_count: number; obligated: string | number; potential: string | number; latest_end?: string | null };
type Summary = {
  filters: { agency: string; naics: string; psc: string; recipient: string };
  totals: { records: number; obligated: string | number; potential: string | number };
  past_winners: Winner[];
  likely_incumbent: Winner | null;
  latest_awards: Array<{ source_id: string; award_number: string; recipient_name: string; awarding_agency: string; obligated_amount: string | number; start_date?: string | null; end_date?: string | null }>;
  classification: string;
  warning: string;
};
type Run = { id: number; status: string; records_seen: number; records_created: number; records_updated: number; errors: string[]; completed_at?: string | null };
type Ingestion = { runs: Run[]; stored_awards: number };

const emptySummary: Summary = { filters: { agency: "", naics: "", psc: "", recipient: "" }, totals: { records: 0, obligated: 0, potential: 0 }, past_winners: [], likely_incumbent: null, latest_awards: [], classification: "official_historical_awards", warning: "No matching award evidence is stored yet." };
const money = (value: string | number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value || 0));

export default function AwardIntelligencePage() {
  const [summary, setSummary] = useState<Summary>(emptySummary);
  const [ingestion, setIngestion] = useState<Ingestion>({ runs: [], stored_awards: 0 });
  const [agency, setAgency] = useState("");
  const [naics, setNaics] = useState("");
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    const [summaryData, ingestionData] = await Promise.all([
      apiGet<Summary>(`/intelligence/awards/summary/?agency=${encodeURIComponent(agency)}&naics=${encodeURIComponent(naics)}`),
      apiGet<Ingestion>("/intelligence/awards/ingestion/"),
    ]);
    setSummary(summaryData);
    setIngestion(ingestionData);
  }, [agency, naics]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load().catch(error => setMessage(error instanceof Error ? error.message : "Award intelligence could not be loaded.")), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function search(event: FormEvent) {
    event.preventDefault();
    setBusy("search");
    setMessage("");
    try { await load(); } catch (error) { setMessage(error instanceof Error ? error.message : "Search failed."); } finally { setBusy(""); }
  }

  async function sync() {
    setBusy("sync");
    setMessage("");
    try {
      const result = await apiPost<Run>("/intelligence/awards/ingestion/", { pages: 3, limit: 100, agency, naics });
      setMessage(`Sync ${result.status}: ${result.records_created} created and ${result.records_updated} updated.`);
      await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Award sync failed."); } finally { setBusy(""); }
  }

  const syncHealth = useMemo(() => ingestion.runs[0]?.status ?? "not_run", [ingestion]);

  return <div className="page-stack award-intelligence-page">
    <section className="page-hero award-intelligence-hero"><div><span className="eyebrow">OFFICIAL FEDERAL AWARD DATA</span><h1>Award Intelligence</h1><p>Ingest USAspending records, identify historical winners, and build evidence-backed incumbent signals without presenting inference as confirmed fact.</p></div><button className="button solid" onClick={() => void sync()} disabled={busy === "sync"}><RefreshCw size={17}/>{busy === "sync" ? "Synchronizing…" : "Sync USAspending"}</button></section>
    {message && <div className="system-banner warning"><TriangleAlert size={18}/><span>{message}</span></div>}
    <form className="award-intelligence-filters" onSubmit={search}><label>Agency<input value={agency} onChange={event => setAgency(event.target.value)} placeholder="Department of the Army"/></label><label>NAICS<input value={naics} onChange={event => setNaics(event.target.value)} placeholder="811310"/></label><button className="button secondary" disabled={busy === "search"}><Search size={16}/>Research awards</button></form>
    <section className="award-intelligence-metrics"><article><Database/><span><small>Stored USAspending awards</small><strong>{ingestion.stored_awards.toLocaleString()}</strong></span></article><article><BadgeDollarSign/><span><small>Matching obligations</small><strong>{money(summary.totals.obligated)}</strong></span></article><article><Activity/><span><small>Matching records</small><strong>{summary.totals.records.toLocaleString()}</strong></span></article><article><ShieldCheck/><span><small>Latest sync</small><strong>{syncHealth.replaceAll("_", " ")}</strong></span></article></section>
    <section className="award-intelligence-grid"><article className="intelligence-panel"><span className="eyebrow">INCUMBENT SIGNAL</span><h2>{summary.likely_incumbent?.recipient_name || "No reliable evidence found"}</h2>{summary.likely_incumbent ? <dl><div><dt>Historical awards</dt><dd>{summary.likely_incumbent.award_count}</dd></div><div><dt>Obligated value</dt><dd>{money(summary.likely_incumbent.obligated)}</dd></div><div><dt>Latest end</dt><dd>{summary.likely_incumbent.latest_end || "Unknown"}</dd></div></dl> : <p>Run a sync or broaden the agency and NAICS filters.</p>}<div className="evidence-note"><ShieldCheck size={16}/><span>{summary.warning}</span></div></article><article className="intelligence-panel"><span className="eyebrow">PAST WINNERS</span><h2>Historical award concentration</h2><div className="winner-list">{summary.past_winners.map((winner, index) => <div key={`${winner.recipient_name}-${index}`}><span>{index + 1}</span><div><strong><CompanyIdentity name={winner.recipient_name} compact/></strong><small>{winner.award_count} awards · {money(winner.obligated)}</small></div></div>)}{summary.past_winners.length === 0 && <p>No matching award records are stored.</p>}</div></article></section>
    <section className="intelligence-panel"><span className="eyebrow">RECENT EVIDENCE</span><h2>Latest matching federal awards</h2><div className="award-evidence-list">{summary.latest_awards.map(row => <article key={row.source_id}><div><strong>{row.recipient_name || "Unknown recipient"}</strong><p>{row.awarding_agency || "Agency unavailable"}</p></div><span>{money(row.obligated_amount)}</span><small>{row.award_number || row.source_id}</small></article>)}{summary.latest_awards.length === 0 && <p>No matching awards available.</p>}</div></section>
  </div>;
}
