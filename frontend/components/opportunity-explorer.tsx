"use client";

import { FormEvent, useMemo, useState } from "react";
import { ArrowDownToLine, ChevronLeft, ChevronRight, ExternalLink, Save, Search, Target } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { API_BASE_URL, apiPost } from "@/lib/api";

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

const copy = {
  "federal-contracts": ["Federal Contract Opportunities", "Search the live SAM.gov Contract Opportunities API and move qualified work directly into your capture pipeline."],
  "federal-forecasts": ["Federal Forecasts", "Agency forecast connectors are being added as source-specific feeds."],
  "federal-vehicles": ["Federal Contract Vehicle Opportunities", "Task-order and contract-vehicle connectors are being added."],
  "state-local": ["State and Local Contract Opportunities", "State and local connectors require source-by-source configuration."],
  "federal-grants": ["Federal Grant Opportunities", "Search live Grants.gov opportunities, save searches, export results, and move qualified grants into the same ForgeGov pipeline."],
} as const;

export function OpportunityExplorer({ mode }: { mode: OpportunityMode }) {
  const sp = useSearchParams();
  const isSam = mode === "federal-contracts";
  const isGrants = mode === "federal-grants";
  const live = isSam || isGrants;
  const [filters, setFilters] = useState({
    q: sp.get("q") ?? "", agency: "", naics: "", psc: "", state: "", set_aside: "",
    posted_from: "", posted_to: "", opportunity_number: "", aln: "", funding_categories: "",
    eligibilities: "", funding_instruments: "", statuses: "forecasted|posted", sort_by: "",
  });
  const [result, setResult] = useState<SearchResult | null>(null);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(isGrants ? "Ready to search live Grants.gov opportunities." : "Ready to search live federal notices.");
  const [busyId, setBusyId] = useState("");

  const page = result ? Math.floor(result.offset / result.limit) + 1 : 1;
  const totalPages = result ? Math.max(1, Math.ceil(result.total_records / result.limit)) : 1;
  const rows = result?.opportunities ?? [];

  function update(name: string, value: string) { setFilters((current) => ({ ...current, [name]: value })); }

  async function search(offset = 0) {
    if (!live) { setMessage("This connector is not configured yet. ForgeGov will not display mock live records."); return; }
    setLoading(true); setMessage("");
    const params = new URLSearchParams({ limit: String(pageSize), offset: String(offset), persist: "true" });
    const allowed = isGrants
      ? ["q", "agency", "opportunity_number", "aln", "funding_categories", "eligibilities", "funding_instruments", "statuses", "sort_by"]
      : ["q", "agency", "naics", "psc", "state", "set_aside", "posted_from", "posted_to"];
    allowed.forEach((key) => { const value = filters[key as keyof typeof filters]; if (value) params.set(key, value); });
    const endpoint = isGrants ? "/live/grants/opportunities/" : "/live/sam/opportunities/";
    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}?${params}`, { cache: "no-store" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail ?? "Live opportunity search failed");
      setResult(data);
      setMessage(`${Number(data.total_records ?? 0).toLocaleString()} matching opportunities. Page ${Math.floor(data.offset / data.limit) + 1} of ${Math.max(1, Math.ceil(data.total_records / data.limit))}.`);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (error) { setMessage(error instanceof Error ? error.message : "Search failed"); }
    finally { setLoading(false); }
  }

  async function submit(event: FormEvent) { event.preventDefault(); await search(0); }

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

  const agencies = useMemo(() => new Set(rows.map((row) => row.fullParentPathName ?? row.agencyName ?? row.agencyCode).filter(Boolean)).size, [rows]);

  function exportCsv() {
    const headers = ["Title","Opportunity number","Agency","Status/type","NAICS/ALN","Posted","Deadline","URL"];
    const esc = (value: unknown) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const body = rows.map((row) => [
      row.title, row.solicitationNumber ?? row.number, row.fullParentPathName ?? row.agencyName ?? row.agencyCode,
      row.type ?? row.oppStatus, row.naicsCode ?? row.alnist?.join("; "), row.postedDate ?? row.openDate,
      row.responseDeadLine ?? row.closeDate, row.uiLink ?? row.source_url,
    ].map(esc).join(","));
    const anchor = document.createElement("a");
    anchor.href = URL.createObjectURL(new Blob([[headers.map(esc).join(","), ...body].join("\n")], { type: "text/csv" }));
    anchor.download = isGrants ? "forgegov-federal-grants.csv" : "forgegov-federal-contracts.csv";
    anchor.click(); URL.revokeObjectURL(anchor.href);
  }

  return <>
    <header className="feature-hero"><div><span className="eyebrow">Opportunity intelligence</span><h1>{copy[mode][0]}</h1><p>{copy[mode][1]}</p></div></header>
    <section className="insight-strip"><div><span>Total matches</span><strong>{result?.total_records?.toLocaleString() ?? "—"}</strong></div><div><span>Current page</span><strong>{page} / {totalPages}</strong></div><div><span>Loaded</span><strong>{rows.length}</strong></div><div><span>Agencies</span><strong>{agencies}</strong></div></section>

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
        <button className="primary-button search-submit" disabled={loading}><Search size={17} />{loading ? "Searching…" : "Search live data"}</button>
      </form>
      <p className="inline-message">{message}</p>
    </section>

    <section className="data-panel">
      <div className="data-toolbar"><div className="result-title"><Target size={18} /><strong>Opportunity results</strong><span>{rows.length} loaded</span></div><button className="toolbar-button" onClick={exportCsv} disabled={!rows.length}><ArrowDownToLine size={16} /> Export</button></div>
      {!rows.length ? <div className="table-state"><Search size={28} /><strong>No results loaded</strong><p>Run a live search to retrieve current records.</p></div> :
        <div className="opportunity-results">{rows.map((row, index) => {
          const id = sourceId(row); const url = row.uiLink ?? row.source_url;
          return <article className="opportunity-result-card" key={id || String(index)}>
            <div className="opportunity-result-main">
              <div className="result-meta"><span>{row.type ?? row.oppStatus ?? (isGrants ? "Federal grant" : "Opportunity")}</span><span>{row.solicitationNumber ?? row.number ?? "No number"}</span></div>
              <h3>{row.title ?? "Untitled opportunity"}</h3>
              <p>{row.fullParentPathName ?? row.agencyName ?? row.agencyCode ?? "Agency not provided"}</p>
              <div className="result-facts"><span>Posted: {row.postedDate ?? row.openDate ?? "—"}</span><span>Deadline: {row.responseDeadLine ?? row.closeDate ?? "—"}</span><span>{isGrants ? `ALN: ${row.alnist?.join(", ") || "—"}` : `NAICS: ${row.naicsCode ?? "—"}`}</span></div>
            </div>
            <div className="opportunity-result-actions">
              {url && <a className="secondary-button" href={url} target="_blank" rel="noreferrer"><ExternalLink size={16} /> Source</a>}
              <button className="primary-button" onClick={() => void addToPipeline(row)} disabled={!id || busyId === id}><Target size={16} />{busyId === id ? "Adding…" : "Add to pipeline"}</button>
            </div>
          </article>;
        })}</div>
      }
      {result && <div className="pagination-bar"><button className="secondary-button" disabled={loading || result.offset <= 0} onClick={() => void search(Math.max(0, result.offset - result.limit))}><ChevronLeft size={16} /> Previous</button><span>Page {page.toLocaleString()} of {totalPages.toLocaleString()} · {result.total_records.toLocaleString()} total</span><button className="secondary-button" disabled={loading || result.offset + result.limit >= result.total_records} onClick={() => void search(result.offset + result.limit)}>Next <ChevronRight size={16} /></button></div>}
    </section>
  </>;
}
