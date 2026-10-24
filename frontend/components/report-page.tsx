"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowDownToLine, RefreshCw, Search } from "lucide-react";
import { apiGet } from "@/lib/api";

type ReportRow = { awarding_agency: string; recipient_name?: string; recipient_uei?: string; first_award?: string; latest_award?: string; award_count: number; obligated: number; recipients?: number; share_percent?: number | null };
type Report = { kind: string; source: string; generated_at: string; coverage_note: string; count: number; page: number; total_pages: number; results: ReportRow[]; totals: { records: number; obligated: number; latest_source_update: string | null }; sync: { status: string; last_completed_at: string | null } };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });
const date = (value?: string | null) => value ? new Date(value.length === 10 ? value + "T12:00:00" : value).toLocaleDateString() : "Not reported";

function exportRows(report: Report) {
  const keys: Array<keyof ReportRow> = report.kind === "funding"
    ? ["awarding_agency", "award_count", "recipients", "obligated", "share_percent"]
    : ["recipient_name", "recipient_uei", "awarding_agency", "first_award", "latest_award", "award_count", "obligated"];
  const cell = (value: unknown) => {
    const text = String(value ?? "");
    const safe = typeof value === "string" && /^\s*[=+\-@]/.test(text) ? "'" + text : text;
    return `"${safe.replaceAll('"', '""')}"`;
  };
  const csv = [keys.join(","), ...report.results.map(row => keys.map(key => cell(row[key])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const anchor = document.createElement("a");
  anchor.href = url; anchor.download = `${report.kind}-page-${report.page}.csv`; anchor.click();
  URL.revokeObjectURL(url);
}

export function ReportPage({ type }: { type: "funding" | "new-entrants" }) {
  const [response, setResponse] = useState<Report | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [agency, setAgency] = useState("");
  const [naics, setNaics] = useState("");
  const [days, setDays] = useState("90");
  const [filters, setFilters] = useState({ agency: "", naics: "", days: "90" });
  const [page, setPage] = useState(1);
  const sequence = useRef(0);
  const report = response?.kind === type ? response : null;
  const entrants = type === "new-entrants";
  const load = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true); setError(""); setResponse(null);
    try {
      const params = new URLSearchParams({ ...filters, kind: type, page: String(page) });
      const data = await apiGet<Report>(`/reports/market/?${params}`);
      if (request === sequence.current) setResponse(data);
    } catch (reason) {
      if (request === sequence.current) setError(reason instanceof Error ? reason.message : "Report could not be loaded.");
    } finally { if (request === sequence.current) setLoading(false); }
  }, [filters, page, type]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => { window.clearTimeout(timer); sequence.current += 1; };
  }, [load]);
  function submit(event: FormEvent) {
    event.preventDefault(); setPage(1);
    setFilters({ agency: agency.trim(), naics: naics.trim(), days });
  }
  return <div className="page-stack market-report-page">
    <header className="feature-hero"><div><span className="eyebrow">Market intelligence reports</span><h1>{entrants ? "New Entrants" : "Funding Intelligence"}</h1><p>{entrants ? "Find recipient–agency relationships first observed in your stored federal award history. This is a research signal, not proof that a contractor is new to the market." : "Compare agency obligations, award counts, and recipient coverage in stored USAspending records."}</p></div><button className="secondary-button" disabled={!report?.results.length || loading} onClick={() => report && exportRows(report)}><ArrowDownToLine size={16}/>Export current page</button></header>
    <section className="data-panel"><form className="market-report-filters" onSubmit={submit}>
      <label><span>Awarding agency</span><input value={agency} onChange={event => setAgency(event.target.value)} placeholder="Department or agency"/></label>
      <label><span>NAICS</span><input value={naics} onChange={event => setNaics(event.target.value)} inputMode="numeric" placeholder="541512"/></label>
      {entrants && <label><span>First observed within</span><select value={days} onChange={event => setDays(event.target.value)}><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option></select></label>}
      <button className="primary-button" disabled={loading}><Search size={16}/>Apply filters</button>
    </form></section>
    {error && <div className="system-banner warning" role="alert"><p>{error}</p><button className="secondary-button" onClick={() => void load()}><RefreshCw size={16}/>Retry report</button></div>}
    <section className="insight-strip"><div><span>Stored federal awards</span><strong>{loading ? "—" : report?.totals.records.toLocaleString() ?? "—"}</strong></div><div><span>Stored obligations</span><strong>{loading ? "—" : report ? money.format(report.totals.obligated) : "—"}</strong></div><div><span>{entrants ? "First-observed relationships" : "Agencies"}</span><strong>{loading ? "—" : report?.count.toLocaleString() ?? "—"}</strong></div><div><span>Last ingestion status</span><strong>{report?.sync.status.replaceAll("_", " ") ?? (loading ? "Checking" : "Unavailable")}</strong></div></section>
    <section className="data-panel market-report-results">
      <div className="panel-title-row"><div><span className="eyebrow">Stored USAspending evidence</span><h2>{entrants ? "First observed recipient–agency relationships" : "Agency funding distribution"}</h2><p>{report ? `Last sync attempt finished: ${date(report.sync.last_completed_at)} · Latest source update: ${date(report.totals.latest_source_update)}` : loading ? "Retrieving stored award evidence…" : "Report unavailable. Retry above."}</p></div></div>
      {loading ? <div className="table-state" role="status"><RefreshCw className="spin"/><strong>Loading report…</strong></div> : report && !report.results.length ? <div className="table-state"><strong>No matching award evidence</strong><p>Adjust the agency, NAICS, or first-observed window. Missing history cannot establish that an organization is a new entrant.</p><Link className="secondary-button" href="/intelligence/connectors">Check source coverage</Link></div> : report && <div className="table-wrap"><table className="data-table"><thead><tr>{entrants && <th>Recipient</th>}<th>Agency</th>{entrants ? <><th>First observed award</th><th>Latest award</th></> : <th>Recipients</th>}<th>Awards</th><th>Obligated</th>{!entrants && <th>Share of stored obligations</th>}</tr></thead><tbody>{report.results.map((row, index) => <tr key={`${row.recipient_uei}-${row.awarding_agency}-${index}`}>
        {entrants && <td className="primary-cell"><Link className="text-link" href={`/participants/vendors/profile?name=${encodeURIComponent(row.recipient_name || "")}`}>{row.recipient_name}</Link><span>{row.recipient_uei || "UEI not reported"}</span></td>}
        <td className="primary-cell">{row.awarding_agency ? <Link className="text-link" href={`/intelligence/agency/${encodeURIComponent(row.awarding_agency)}`}>{row.awarding_agency}</Link> : "Agency not reported"}</td>
        {entrants ? <><td>{date(row.first_award)}</td><td>{date(row.latest_award)}</td></> : <td>{row.recipients}</td>}<td>{row.award_count}</td><td>{money.format(row.obligated)}</td>{!entrants && <td>{row.share_percent == null ? "Not available" : `${row.share_percent}%`}</td>}
      </tr>)}</tbody></table></div>}
      {report && <p className="report-coverage-note">{report.coverage_note}</p>}
    </section>
    {report && report.total_pages > 1 && <nav className="pagination-bar" aria-label="Report pages"><button className="secondary-button" disabled={loading || report.page <= 1} onClick={() => setPage(report.page - 1)}>Previous</button><span>Page {report.page} of {report.total_pages}</span><button className="secondary-button" disabled={loading || report.page >= report.total_pages} onClick={() => setPage(report.page + 1)}>Next</button></nav>}
  </div>;
}
