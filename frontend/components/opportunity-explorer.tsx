"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArrowDownToLine, ChevronLeft, ChevronRight, ExternalLink, FileSearch, LoaderCircle, Save, Search, Target } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

export type OpportunityMode = "federal-contracts" | "federal-forecasts" | "federal-vehicles" | "state-local" | "federal-grants";

type LiveOpportunity = {
  noticeId?: string; source_id?: string; id?: string | number; title?: string;
  solicitationNumber?: string; number?: string; fullParentPathName?: string;
  agencyName?: string; agencyCode?: string; postedDate?: string; openDate?: string;
  responseDeadLine?: string; closeDate?: string; uiLink?: string; source_url?: string;
  type?: string; oppStatus?: string; naicsCode?: string; classificationCode?: string;
  typeOfSetAsideDescription?: string; alnist?: string[];
};

type SearchResult = {
  total_records: number; limit: number; offset: number; opportunities: LiveOpportunity[];
  persisted?: { enabled: boolean; created: number; updated: number };
};

type Filters = {
  q: string; agency: string; naics: string; psc: string; state: string; set_aside: string;
  posted_from: string; posted_to: string; opportunity_number: string; aln: string;
  funding_categories: string; eligibilities: string; funding_instruments: string;
  statuses: string; sort_by: string;
};

const copy = {
  "federal-contracts": ["Federal Contract Opportunities", "Search the live SAM.gov Contract Opportunities API and move qualified work directly into your capture pipeline."],
  "federal-forecasts": ["Federal Forecasts", "Agency forecast connectors are being added as source-specific feeds."],
  "federal-vehicles": ["Federal Contract Vehicle Opportunities", "Task-order and contract-vehicle connectors are being added."],
  "state-local": ["State and Local Contract Opportunities", "State and local connectors require source-by-source configuration."],
  "federal-grants": ["Federal Grant Opportunities", "Search live Grants.gov opportunities, save searches, export results, and move qualified grants into the same ForgeGov pipeline."],
} as const;


function defaultFilters(query = ""): Filters {
  return {
    q: query, agency: "", naics: "", psc: "", state: "", set_aside: "",
    posted_from: "", posted_to: "", opportunity_number: "", aln: "", funding_categories: "",
    eligibilities: "", funding_instruments: "", statuses: "forecasted|posted", sort_by: "",
  };
}

function hasCustomFilters(filters: Filters, isGrants: boolean) {
  const ignored = new Set(isGrants ? ["statuses", "sort_by"] : []);
  return Object.entries(filters).some(([key, value]) => !ignored.has(key) && value.trim() !== "")
    || (isGrants && filters.statuses !== "forecasted|posted")
    || (isGrants && filters.sort_by.trim() !== "");
}

function recentTimestamp(row: LiveOpportunity) {
  const value = row.postedDate ?? row.openDate ?? "";
  const usDate = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(value.trim());
  if (usDate) return Date.UTC(Number(usDate[3]), Number(usDate[1]) - 1, Number(usDate[2]));
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}

function agencyName(row: LiveOpportunity) {
  return row.fullParentPathName ?? row.agencyName ?? row.agencyCode ?? "Agency not provided";
}
function grantOpportunityId(row: LiveOpportunity) {
  return String(row.id ?? row.source_id ?? "").replace(/^grants\.gov:/, "");
}
function detailHref(row: LiveOpportunity, isGrants: boolean) {
  if (isGrants) { const id = grantOpportunityId(row); return id ? `/opportunities/federal-grants/${encodeURIComponent(id)}` : ""; }
  const id = row.source_id ?? row.noticeId ?? "";
  return id ? `/opportunities/federal-contracts/${encodeURIComponent(String(id))}` : "";
}

export function OpportunityExplorer({ mode }: { mode: OpportunityMode }) {
  const sp = useSearchParams();
  const queryFromUrl = sp.get("q") ?? "";
  const autoSearch = sp.get("auto") === "1";
  const lastUrlQuery = useRef(queryFromUrl);
  const lastAutoSearch = useRef("");
  const initialLoadMode = useRef("");
  const isSam = mode === "federal-contracts";
  const isGrants = mode === "federal-grants";
  const live = isSam || isGrants;
  const [filters, setFilters] = useState<Filters>(() => defaultFilters(sp.get("q") ?? ""));
  const [result, setResult] = useState<SearchResult | null>(null);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [showingRecent, setShowingRecent] = useState(true);
  const [message, setMessage] = useState(live ? "Loading the most recent live opportunities…" : "This connector is not configured yet.");
  const [busyId, setBusyId] = useState("");

  const page = result ? Math.floor(result.offset / result.limit) + 1 : 1;
  const totalPages = result ? Math.max(1, Math.ceil(result.total_records / result.limit)) : 1;
  const rows = useMemo(() => result?.opportunities ?? [], [result]);
  const displayRows = useMemo(() => showingRecent ? [...rows].sort((left, right) => recentTimestamp(right) - recentTimestamp(left)) : rows, [rows, showingRecent]);

  function update(name: keyof Filters, value: string) { setFilters((current) => ({ ...current, [name]: value })); }

  const search = useCallback(async (offset = 0, selectedFilters = filters) => {
    if (!live) { setMessage("This connector is not configured yet. ForgeGov will not display mock live records."); return; }
    const recentView = !hasCustomFilters(selectedFilters, isGrants);
    setShowingRecent(recentView);
    setLoading(true);
    setMessage(recentView ? "Refreshing the latest live opportunities…" : "Searching live opportunity data…");
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset), persist: "true" });
    const allowed: Array<keyof Filters> = isGrants
      ? ["q", "agency", "opportunity_number", "aln", "funding_categories", "eligibilities", "funding_instruments", "statuses", "sort_by"]
      : ["q", "agency", "naics", "psc", "state", "set_aside", "posted_from", "posted_to"];
    allowed.forEach((key) => { const value = selectedFilters[key]; if (value) params.set(key, value); });
    const endpoint = isGrants ? "/live/grants/opportunities/" : "/live/sam/opportunities/";
    try {
      const data = await apiGet<SearchResult>(`${endpoint}?${params.toString()}`);
      setResult(data);
      const pageNumber = Math.floor(data.offset / data.limit) + 1;
      const pageTotal = Math.max(1, Math.ceil(data.total_records / data.limit));
      setMessage(recentView
        ? `Loaded the latest ${Number(data.opportunities?.length ?? 0).toLocaleString()} records from ${isGrants ? "Grants.gov" : "SAM.gov"}. ${Number(data.total_records ?? 0).toLocaleString()} active matches are available.`
        : `${Number(data.total_records ?? 0).toLocaleString()} matching opportunities. Page ${pageNumber} of ${pageTotal}.`);
      if (offset > 0) window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) {
      setResult(null);
      setMessage(error instanceof Error ? error.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }, [filters, isGrants, live, pageSize]);

  useEffect(() => {
    if (initialLoadMode.current === mode) return;
    initialLoadMode.current = mode;
    const timer = window.setTimeout(() => {
      const selectedFilters = defaultFilters(queryFromUrl);
      setFilters(selectedFilters); setResult(null); setShowingRecent(true);
      if (!live) { setLoading(false); setMessage("This connector is not configured yet. ForgeGov will not display mock live records."); return; }
      if (autoSearch && queryFromUrl) lastAutoSearch.current = queryFromUrl;
      void search(0, selectedFilters);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [autoSearch, live, mode, queryFromUrl, search]);

  useEffect(() => {
    if (!queryFromUrl) return;
    const timer = window.setTimeout(() => {
      const selectedFilters = { ...filters, q: queryFromUrl };
      if (lastUrlQuery.current !== queryFromUrl) { lastUrlQuery.current = queryFromUrl; setFilters(selectedFilters); }
      if (autoSearch && live && lastAutoSearch.current !== queryFromUrl) { lastAutoSearch.current = queryFromUrl; void search(0, selectedFilters); }
    }, 0);
    return () => window.clearTimeout(timer);
  }, [autoSearch, filters, live, queryFromUrl, search]);

  async function submit(event: FormEvent) { event.preventDefault(); await search(0, filters); }

  async function saveSearch() {
    const defaultName = filters.q ? `${filters.q} ${isGrants ? "grants" : "opportunities"}` : `${copy[mode][0]} search`;
    const name = window.prompt("Name this search", defaultName);
    if (!name) return;
    try {
      await apiPost("/workflow/saved-searches/", { name, filters: { source: isGrants ? "grants.gov" : "sam.gov", ...filters } });
      setMessage(`Saved search “${name}”.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not save search"); }
  }

  function sourceId(row: LiveOpportunity) { return row.source_id ?? row.noticeId ?? (isGrants && row.id ? `grants.gov:${row.id}` : ""); }

  async function addToPipeline(row: LiveOpportunity) {
    const id = sourceId(row);
    if (!id) return;
    setBusyId(id);
    try {
      await apiPost("/workflow/opportunity-to-pipeline/", { source_id: id, stage: "reviewing" });
      setMessage(`Added “${row.title ?? "opportunity"}” to the pipeline.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "Could not add to pipeline"); }
    finally { setBusyId(""); }
  }

  const agencies = useMemo(() => new Set(displayRows.map((row) => row.fullParentPathName ?? row.agencyName ?? row.agencyCode).filter(Boolean)).size, [displayRows]);

  function exportCsv() {
    const headers = ["Title","Opportunity number","Agency","Status/type","NAICS/ALN","Posted","Deadline","URL"];
    const esc = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const body = displayRows.map((row) => [
      row.title, row.solicitationNumber ?? row.number, row.fullParentPathName ?? row.agencyName ?? row.agencyCode,
      row.type ?? row.oppStatus, row.naicsCode ?? row.alnist?.join("; "), row.postedDate ?? row.openDate,
      row.responseDeadLine ?? row.closeDate, row.source_url ?? row.uiLink,
    ].map(esc).join(","));
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(new Blob([[headers.map(esc).join(","), ...body].join("\n")], { type: "text/csv" }));
    anchor.download = isGrants ? "forgegov-federal-grants.csv" : "forgegov-federal-contracts.csv";
    anchor.click(); URL.revokeObjectURL(anchor.href);
  }

  return <>
    <header className="feature-hero"><div><span className="eyebrow">Opportunity intelligence</span><h1>{copy[mode][0]}</h1><p>{copy[mode][1]}</p></div></header>
    <section className="insight-strip"><div><span>Total matches</span><strong>{result?.total_records?.toLocaleString() ?? "—"}</strong></div><div><span>Current page</span><strong>{page} / {totalPages}</strong></div><div><span>Loaded</span><strong>{displayRows.length}</strong></div><div><span>Agencies</span><strong>{agencies}</strong></div></section>

    <section className="data-panel opportunity-search-panel">
      <form className="advanced-filter-grid" onSubmit={submit}>
        <label><span>Keywords</span><input value={filters.q} onChange={(event) => update("q", event.target.value)} placeholder={isGrants ? "rural health, workforce, infrastructure" : "maintenance, logistics, IT support"} /></label>
        <label><span>Agency</span><input value={filters.agency} onChange={(event) => update("agency", event.target.value)} placeholder={isGrants ? "HHS, USDA, DOE" : "Department of the Navy"} /></label>
        {isGrants ? <>
          <label><span>Opportunity number</span><input value={filters.opportunity_number} onChange={(event) => update("opportunity_number", event.target.value)} /></label>
          <label><span>ALN / CFDA</span><input value={filters.aln} onChange={(event) => update("aln", event.target.value)} placeholder="93.866" /></label>
          <label><span>Funding category code</span><input value={filters.funding_categories} onChange={(event) => update("funding_categories", event.target.value)} placeholder="HL" /></label>
          <label><span>Eligibility code</span><input value={filters.eligibilities} onChange={(event) => update("eligibilities", event.target.value)} placeholder="01" /></label>
          <label><span>Funding instrument</span><input value={filters.funding_instruments} onChange={(event) => update("funding_instruments", event.target.value)} placeholder="G" /></label>
          <label><span>Status</span><select value={filters.statuses} onChange={(event) => update("statuses", event.target.value)}><option value="forecasted|posted">Forecasted + posted</option><option value="posted">Posted</option><option value="forecasted">Forecasted</option><option value="closed">Closed</option><option value="archived">Archived</option></select></label>
        </> : <>
          <label><span>NAICS</span><input value={filters.naics} onChange={(event) => update("naics", event.target.value)} placeholder="811111" /></label>
          <label><span>PSC</span><input value={filters.psc} onChange={(event) => update("psc", event.target.value)} placeholder="J023" /></label>
          <label><span>State</span><input value={filters.state} onChange={(event) => update("state", event.target.value)} maxLength={2} /></label>
          <label><span>Set-aside code</span><input value={filters.set_aside} onChange={(event) => update("set_aside", event.target.value)} /></label>
          <label><span>Posted from</span><input type="date" value={filters.posted_from} onChange={(event) => update("posted_from", event.target.value)} /></label>
          <label><span>Posted to</span><input type="date" value={filters.posted_to} onChange={(event) => update("posted_to", event.target.value)} /></label>
        </>}
        <label><span>Results per page</span><select value={pageSize} onChange={(event) => setPageSize(Number(event.target.value))}><option>25</option><option>50</option><option>100</option></select></label>
        <button className="secondary-button" type="button" onClick={saveSearch}><Save size={16} /> Save search</button>
        <button className="primary-button search-submit" disabled={loading || !live}>{loading ? <LoaderCircle className="spin" size={17} /> : <Search size={17} />}{loading ? "Loading…" : "Search live data"}</button>
      </form>
      <p className="inline-message">{message}</p>
    </section>

    <section className="data-panel">
      <div className="data-toolbar"><div className="result-title"><Target size={18} /><strong>{showingRecent ? "Latest opportunity results" : "Opportunity results"}</strong><span>{displayRows.length} loaded</span></div><button className="toolbar-button" onClick={exportCsv} disabled={!displayRows.length}><ArrowDownToLine size={16} /> Export</button></div>
      {loading && !result ? <div className="table-state"><LoaderCircle className="spin" size={28} /><strong>Loading recent live data</strong><p>ForgeGov is requesting the newest available records from the source.</p></div> :
        !displayRows.length ? <div className="table-state"><Search size={28} /><strong>{live ? "No results found" : "Connector not configured"}</strong><p>{live ? "Try changing the filters or refreshing the page." : "ForgeGov will show live records here when this source connector is added."}</p></div> :
        <div className="opportunity-results">{displayRows.map((row, index) => {
          const id = sourceId(row); const url = row.source_url ?? row.uiLink; const href = detailHref(row, isGrants); const agency = agencyName(row);
          return <article className={`opportunity-result-card interactive-opportunity-card ${isGrants ? "grant-result-card" : "contract-result-card"}`} key={id || String(index)}>
            <div className="opportunity-result-main">
              <div className="result-source-row"><span className={`source-chip ${isGrants ? "grant-source-chip" : "contract-source-chip"}`}>{isGrants ? "LIVE GRANTS.GOV" : "LIVE SAM.GOV"}</span><span>{row.type ?? row.oppStatus ?? (isGrants ? "Federal grant" : "Contract opportunity")}</span><span>{row.solicitationNumber ?? row.number ?? "No number"}</span></div>
              {href ? <Link className="opportunity-title-link" href={href}><h3>{row.title ?? "Untitled opportunity"}</h3></Link> : <h3>{row.title ?? "Untitled opportunity"}</h3>}
              <Link className="opportunity-agency-link" href={`/intelligence/agency/${encodeURIComponent(agency)}`}>{agency} <ExternalLink size={13}/></Link>
              <div className="result-facts"><span>Posted: {row.postedDate ?? row.openDate ?? "—"}</span><span>Deadline: {row.responseDeadLine ?? row.closeDate ?? "—"}</span><span>{isGrants ? `ALN: ${row.alnist?.join(", ") || "—"}` : `NAICS: ${row.naicsCode ?? "—"}`}</span></div>
            </div>
            <div className="opportunity-result-actions">
              {href && <Link className="secondary-button" href={href}><FileSearch size={16} /> {isGrants ? "Grant workspace" : "Details & files"}</Link>}
              {url && <a className="secondary-button" href={url} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Official source</a>}
              <button className="primary-button" onClick={() => void addToPipeline(row)} disabled={!id || busyId === id}><Target size={16} />{busyId === id ? "Adding…" : "Add to pipeline"}</button>
            </div>
          </article>;
        })}</div>
      }
      {result && <div className="pagination-bar"><button className="secondary-button" disabled={loading || result.offset <= 0} onClick={() => void search(Math.max(0, result.offset - result.limit), filters)}><ChevronLeft size={16} /> Previous</button><span>Page {page.toLocaleString()} of {totalPages.toLocaleString()} · {result.total_records.toLocaleString()} total</span><button className="secondary-button" disabled={loading || result.offset + result.limit >= result.total_records} onClick={() => void search(result.offset + result.limit, filters)}>Next <ChevronRight size={16} /></button></div>}
    </section>
  </>;
}
