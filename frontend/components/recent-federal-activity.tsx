"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, BriefcaseBusiness, CalendarClock, Database, FileSearch, RefreshCw, Search } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type FeedKind = "opportunities" | "awards";
type FeedRow = {
  id: number; source_id: string; title?: string; description?: string; agency?: string; office?: string;
  solicitation_number?: string; award_number?: string; recipient_name?: string; awarding_agency?: string;
  obligated_amount?: number | string; naics_code?: string; psc_code?: string; notice_type?: string;
  posted_date?: string | null; response_deadline?: string | null; start_date?: string | null;
  source_updated_at?: string | null; source_url?: string;
};
type FeedResponse = {
  kind: FeedKind; count: number; page: number; page_size: number; total_pages: number;
  next_page: number | null; previous_page: number | null; results: FeedRow[];
  sync: { status: string; last_completed_at: string | null; records_seen: number; records_created?: number; records_updated?: number };
};

const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });

function readableDate(value?: string | null) {
  if (!value) return "Not reported";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not reported" : date.toLocaleDateString();
}

function officialUrl(kind: FeedKind, row: FeedRow) {
  if (row.source_url) return row.source_url;
  if (kind === "opportunities") return `https://sam.gov/opp/${encodeURIComponent(row.source_id)}/view`;
  return `https://www.usaspending.gov/award/${encodeURIComponent(row.source_id)}/`;
}

export function RecentFederalActivity() {
  const [kind, setKind] = useState<FeedKind>("opportunities");
  const [query, setQuery] = useState("");
  const [agency, setAgency] = useState("");
  const [naics, setNaics] = useState("");
  const [psc, setPsc] = useState("");
  const [filters, setFilters] = useState({ query: "", agency: "", naics: "", psc: "" });
  const [page, setPage] = useState(1);
  const [responseData, setData] = useState<FeedResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [adding, setAdding] = useState("");
  const requestSequence = useRef(0);

  const load = useCallback(async () => {
    const request = ++requestSequence.current;
    setLoading(true);
    setError("");
    setData(null);
    const params = new URLSearchParams({ kind, page: String(page), page_size: "20" });
    if (filters.query) params.set("q", filters.query);
    if (filters.agency) params.set("agency", filters.agency);
    if (filters.naics) params.set("naics", filters.naics);
    if (filters.psc) params.set("psc", filters.psc);
    try {
      const response = await apiGet<FeedResponse>(`/intelligence/recent-federal-activity/?${params}`);
      if (request === requestSequence.current) setData(response);
    } catch (requestError) {
      if (request === requestSequence.current) setError(requestError instanceof Error ? requestError.message : "Federal activity could not be loaded.");
    } finally {
      if (request === requestSequence.current) setLoading(false);
    }
  }, [filters, kind, page]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => {
      window.clearTimeout(timer);
      requestSequence.current += 1;
    };
  }, [load]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const next = { query: query.trim(), agency: agency.trim(), naics: naics.trim(), psc: psc.trim() };
    if (page === 1 && JSON.stringify(next) === JSON.stringify(filters)) void load();
    else {
      setFilters(next);
      setPage(1);
    }
  }

  async function addToPipeline(row: FeedRow) {
    setAdding(row.source_id);
    setMessage("");
    try {
      await apiPost("/workflow/opportunity-to-pipeline/", { source_id: row.source_id, stage: "reviewing" });
      setMessage(`Added “${row.title || "opportunity"}” to the capture pipeline.`);
    } catch (requestError) {
      setMessage(requestError instanceof Error ? requestError.message : "Opportunity could not be added to the pipeline.");
    } finally {
      setAdding("");
    }
  }

  // A source switch renders before its effect runs. Never label the prior source as the new one.
  const data = responseData?.kind === kind ? responseData : null;
  const syncStatus = data?.sync.status?.replaceAll("_", " ") || "not run";
  const syncNeedsAttention = ["failed", "partial", "stale", "not_run"].includes(data?.sync.status || "not_run");

  return <main className="page-stack federal-activity-page">
    <section className="feature-hero federal-activity-hero">
      <div><span className="page-kicker">FEDERAL MARKET FEED</span><h1>Recent Federal Activity</h1><p>Review synchronized SAM.gov opportunities and USAspending award activity in one workspace, with official-source links and explicit freshness evidence.</p></div>
      <div className={`federal-sync-state ${syncNeedsAttention ? "attention" : "current"}`}><Database size={19}/><span><b>{syncStatus}</b><small>{data?.sync.last_completed_at ? `Last completed ${new Date(data.sync.last_completed_at).toLocaleString()}` : "No completed sync has been recorded"}</small></span></div>
    </section>

    <section className="data-panel federal-feed-controls">
      <div className="federal-feed-tabs" role="tablist" aria-label="Federal activity source">
        <button type="button" role="tab" aria-selected={kind === "opportunities"} className={kind === "opportunities" ? "active" : ""} onClick={() => { setKind("opportunities"); setPage(1); }}><FileSearch size={17}/> SAM.gov opportunities</button>
        <button type="button" role="tab" aria-selected={kind === "awards"} className={kind === "awards" ? "active" : ""} onClick={() => { setKind("awards"); setPage(1); }}><BriefcaseBusiness size={17}/> USAspending awards</button>
      </div>
      <form className="federal-feed-filter-grid" onSubmit={submit}>
        <label><span>Keyword</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Title, award, recipient…"/></label>
        <label><span>Agency</span><input value={agency} onChange={(event) => setAgency(event.target.value)} placeholder="Department or office"/></label>
        <label><span>NAICS</span><input value={naics} onChange={(event) => setNaics(event.target.value)} inputMode="numeric" placeholder="541512"/></label>
        <label><span>PSC</span><input value={psc} onChange={(event) => setPsc(event.target.value)} placeholder="D302"/></label>
        <button className="primary-button" type="submit"><Search size={16}/> Search</button>
      </form>
    </section>

    {message && <div className="alert-strip" role="status"><span>{message}</span></div>}
    {error && <div className="alert-strip" role="alert"><b>Feed unavailable.</b><span>{error}</span><button className="secondary-button" onClick={() => void load()}><RefreshCw size={15}/> Retry</button></div>}

    <section className="data-panel federal-feed-results" aria-live="polite">
      <header className="panel-title-row"><div><span className="panel-kicker">{kind === "opportunities" ? "SAM.GOV" : "USASPENDING.GOV"}</span><h2>{kind === "opportunities" ? "Recently posted opportunities" : "Recent contract awards and spending"}</h2><p>{data ? `${data.count.toLocaleString()} synchronized record${data.count === 1 ? "" : "s"}` : "Loading synchronized records…"}</p></div><button className="secondary-button" onClick={() => void load()} disabled={loading}><RefreshCw size={15}/> Refresh view</button></header>
      {loading ? <div className="table-state" role="status"><strong>Loading recent federal activity…</strong></div> : null}
      {!loading && !error && !data?.results.length ? <div className="table-state"><strong>No synchronized records match these filters.</strong><span>Check Connector Manager for sync evidence or use the live source workspaces while the background feed is populated.</span><Link className="secondary-button" href={kind === "opportunities" ? "/opportunities/federal-contracts" : "/awards/federal-contracts"}>Open live search</Link></div> : null}
      {!loading && data?.results.length ? <div className="federal-feed-list">{data.results.map((row) => <article key={`${kind}-${row.id}`} className="federal-feed-card">
        <div className="federal-feed-card-main"><span className="feed-source-label">{kind === "opportunities" ? row.notice_type || "Opportunity" : "Contract award"}</span><h3>{kind === "opportunities" ? row.title || "Untitled opportunity" : row.description || row.award_number || "Federal award"}</h3><p>{kind === "opportunities" ? [row.agency, row.office].filter(Boolean).join(" · ") || "Agency not reported" : [row.recipient_name, row.awarding_agency].filter(Boolean).join(" · ") || "Recipient or agency not reported"}</p><div className="federal-feed-facts"><span><CalendarClock size={13}/>{kind === "opportunities" ? `Posted ${readableDate(row.posted_date)}` : `Start ${readableDate(row.start_date)}`}</span>{kind === "opportunities" && <span>Due {readableDate(row.response_deadline)}</span>}{kind === "awards" && <span>{money.format(Number(row.obligated_amount || 0))} obligated</span>}{row.naics_code && <span>NAICS {row.naics_code}</span>}{row.psc_code && <span>PSC {row.psc_code}</span>}</div></div>
        <div className="federal-feed-card-actions">{kind === "opportunities" && <button className="primary-button" disabled={adding === row.source_id} onClick={() => void addToPipeline(row)}>{adding === row.source_id ? "Adding…" : "Add to pipeline"}</button>}<a className="secondary-button" href={officialUrl(kind, row)} target="_blank" rel="noreferrer">Official source <ArrowUpRight size={14}/></a>{kind === "opportunities" && <Link className="secondary-button" href={`/opportunities/federal-contracts/${encodeURIComponent(row.source_id)}`}>Open workspace</Link>}</div>
      </article>)}</div> : null}
      {data && data.total_pages > 1 && <nav className="pagination-bar" aria-label="Federal activity pages"><button className="secondary-button" disabled={!data.previous_page || loading} onClick={() => setPage(data.previous_page || 1)}>Previous</button><span>Page {data.page} of {data.total_pages}</span><button className="secondary-button" disabled={!data.next_page || loading} onClick={() => setPage(data.next_page || data.page)}>Next</button></nav>}
    </section>
  </main>;
}
