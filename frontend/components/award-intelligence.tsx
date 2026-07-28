"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, Building2, Database, Download, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import { API_BASE_URL, apiGet } from "@/lib/api";

type UsaAward = {
  "Award ID"?: string;
  "Recipient Name"?: string;
  "Award Amount"?: number;
  "Description"?: string;
  "Start Date"?: string;
  "End Date"?: string;
  "Awarding Agency"?: string;
  "Funding Agency"?: string;
  generated_unique_award_id?: string;
};

type Result = {
  results: UsaAward[];
  page_metadata?: { page?: number; hasNext?: boolean; total?: number };
  persisted?: { enabled: boolean; created: number; updated: number; errors: string[] };
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 });

export function AwardIntelligence() {
  const [query, setQuery] = useState("");
  const [agency, setAgency] = useState("");
  const [recipient, setRecipient] = useState("");
  const [naics, setNaics] = useState("");
  const [data, setData] = useState<Result | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [persist, setPersist] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  const search = useCallback(async (requestedPage: number) => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams({ limit: String(pageSize), page: String(requestedPage), persist: String(persist) });
    if (query) params.set("q", query);
    if (agency) params.set("agency", agency);
    if (recipient) params.set("recipient", recipient);
    if (naics) params.set("naics", naics);
    try {
      setData(await apiGet<Result>(`/live/usaspending/awards/?${params.toString()}`));
      setPage(requestedPage);
    } catch (err) {
      setError(err instanceof Error ? err.message : "USAspending search failed");
    } finally {
      setLoading(false);
    }
  }, [agency, naics, pageSize, persist, query, recipient]);

  const initialSearch = useRef(search);
  useEffect(() => {
    const timer = window.setTimeout(() => void initialSearch.current(1), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const total = useMemo(() => (data?.results ?? []).reduce((sum, item) => sum + Number(item["Award Amount"] ?? 0), 0), [data]);
  const agencies = useMemo(() => new Set((data?.results ?? []).map((item) => item["Awarding Agency"]).filter(Boolean)).size, [data]);
  const recipients = useMemo(() => new Set((data?.results ?? []).map((item) => item["Recipient Name"]).filter(Boolean)).size, [data]);

  function exportCsv() {
    const rows = data?.results ?? [];
    const header = ["Award ID", "Recipient", "Agency", "Amount", "Start Date", "End Date", "Description"];
    const escape = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const csv = [header, ...rows.map((r) => [r["Award ID"], r["Recipient Name"], r["Awarding Agency"], r["Award Amount"], r["Start Date"], r["End Date"], r["Description"]])]
      .map((row) => row.map(escape).join(",")).join("\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    link.download = "forgegov-usaspending-awards.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div className="intelligence-page">
      <section className="intel-hero">
        <div>
          <span className="eyebrow">LIVE FEDERAL AWARD INTELLIGENCE</span>
          <h1>USAspending Awards</h1>
          <p>Search live federal contract awards, persist results to ForgeGov, and build agency and vendor intelligence from the same records.</p>
        </div>
        <div className="live-pill"><span /> Live public API</div>
      </section>

      <section className="search-console">
        <div className="search-console-grid">
          <label><span>Keyword</span><div><Search size={17}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="JLTV, maintenance, logistics..." /></div></label>
          <label><span>Awarding agency</span><input value={agency} onChange={(e) => setAgency(e.target.value)} placeholder="Department of Defense" /></label>
          <label><span>Recipient</span><input value={recipient} onChange={(e) => setRecipient(e.target.value)} placeholder="Company name" /></label>
          <label><span>NAICS</span><input value={naics} onChange={(e) => setNaics(e.target.value)} placeholder="811111" /></label>
          <label><span>Results per page</span><select value={pageSize} onChange={(e) => setPageSize(Number(e.target.value))}><option>25</option><option>50</option><option>100</option></select></label>
        </div>
        <div className="console-actions">
          <label className="persist-check"><input type="checkbox" checked={persist} onChange={(e) => setPersist(e.target.checked)} /> Store results in ForgeGov</label>
          <button className="secondary-button" onClick={exportCsv} disabled={!data?.results?.length}><Download size={16}/> Export CSV</button>
          <button className="primary-button" onClick={() => search(1)} disabled={loading}><RefreshCw size={16} className={loading ? "spin" : ""}/>{loading ? "Searching..." : "Search awards"}</button>
        </div>
      </section>

      {error && <div className="system-banner warning"><strong>USAspending error:</strong> {error}</div>}
      {data?.persisted?.enabled && <div className="system-banner success"><ShieldCheck size={17}/><strong>Database updated:</strong> {data.persisted.created} created, {data.persisted.updated} refreshed.</div>}

      <section className="intel-kpis">
        <div><Database/><span>Results</span><strong>{data?.results?.length ?? 0}</strong></div>
        <div><span className="kpi-symbol">$</span><span>Obligated</span><strong>{money.format(total)}</strong></div>
        <div><Building2/><span>Agencies</span><strong>{agencies}</strong></div>
        <div><Users/><span>Recipients</span><strong>{recipients}</strong></div>
      </section>

      <section className="data-panel award-table-panel">
        <div className="panel-title-row"><div><span className="eyebrow">SEARCH RESULTS</span><h2>Federal contract awards</h2></div><small>Source: USAspending.gov</small></div>
        {!loading && !data?.results?.length ? <div className="table-state"><Database size={30}/><strong>No awards returned</strong><p>Change the filters and search again.</p></div> :
          <div className="award-table-wrap"><table className="award-table"><thead><tr><th>Award / Description</th><th>Recipient</th><th>Agency</th><th>Period</th><th className="amount">Obligated</th></tr></thead><tbody>
            {(data?.results ?? []).map((award, index) => {
              const uid = award.generated_unique_award_id;
              return <tr key={`${uid ?? award["Award ID"]}-${index}`}>
                <td><strong>{award["Award ID"] || "Award"}</strong><span>{award["Description"] || "No description provided"}</span></td>
                <td><strong>{award["Recipient Name"] || "Unknown recipient"}</strong></td>
                <td><strong>{award["Awarding Agency"] || "Unknown agency"}</strong><span>{award["Funding Agency"] && award["Funding Agency"] !== award["Awarding Agency"] ? `Funded by ${award["Funding Agency"]}` : ""}</span></td>
                <td><strong>{award["Start Date"] || "—"}</strong><span>to {award["End Date"] || "—"}</span></td>
                <td className="amount"><strong>{money.format(Number(award["Award Amount"] ?? 0))}</strong>{uid && <a href={`https://www.usaspending.gov/award/${uid}/`} target="_blank" rel="noreferrer">View source <ArrowUpRight size={13}/></a>}</td>
              </tr>;
            })}
          </tbody></table></div>}
      </section>
      {data && <div className="pagination-bar"><button className="secondary-button" disabled={loading || page <= 1} onClick={() => search(page - 1)}>Previous</button><span>Page <strong>{page}</strong>{data.page_metadata?.total ? ` · ${Number(data.page_metadata.total).toLocaleString()} total awards` : ""}</span><button className="secondary-button" disabled={loading || !data.page_metadata?.hasNext} onClick={() => search(page + 1)}>Next</button></div>}
      <p className="source-note">Live endpoint: <code>{API_BASE_URL}/live/usaspending/awards/</code></p>
    </div>
  );
}
