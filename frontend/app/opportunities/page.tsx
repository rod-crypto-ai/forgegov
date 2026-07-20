"use client";
import { FormEvent, useState } from "react";
import { ExternalLink, Search } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { API_BASE } from "@/lib/api";

type SamOpportunity = { noticeId?: string; title?: string; solicitationNumber?: string; fullParentPathName?: string; postedDate?: string; responseDeadLine?: string; uiLink?: string; type?: string; naicsCode?: string; classificationCode?: string; setAside?: string; };

export default function OpportunitiesPage() {
  const [filters, setFilters] = useState({ q: "", agency: "", naics: "", state: "" });
  const [persist, setPersist] = useState(true);
  const [rows, setRows] = useState<SamOpportunity[]>([]);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("Search current SAM.gov notices. Results can be stored in ForgeGov for capture workflows.");
  function update(name: string, value: string) { setFilters((current) => ({ ...current, [name]: value })); }
  async function submit(event: FormEvent) {
    event.preventDefault(); setLoading(true); setMessage("");
    const params = new URLSearchParams({ limit: "25", persist: String(persist), ...filters });
    try {
      const response = await fetch(`${API_BASE}/live/sam/opportunities/?${params}`);
      const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "Search failed.");
      setRows(data.opportunities ?? []);
      const saved = data.persisted?.enabled ? ` Saved ${data.persisted.created ?? 0} new and updated ${data.persisted.updated ?? 0}.` : "";
      setMessage(`${data.total_records ?? 0} matching SAM.gov records found.${saved}`);
    } catch (error) { setRows([]); setMessage(error instanceof Error ? error.message : "Search failed."); }
    finally { setLoading(false); }
  }
  return <>
    <PageHeader eyebrow="Live government data" title="Opportunity search" description="Search SAM.gov through the ForgeGov backend. The API credential is never exposed to the browser." />
    <section className="panel"><form className="filter-grid" onSubmit={submit}>
      <label><span>Title keyword</span><input value={filters.q} onChange={(e)=>update("q",e.target.value)} placeholder="vehicle maintenance" /></label>
      <label><span>Agency</span><input value={filters.agency} onChange={(e)=>update("agency",e.target.value)} placeholder="Department of the Navy" /></label>
      <label><span>NAICS</span><input value={filters.naics} onChange={(e)=>update("naics",e.target.value)} placeholder="811111" /></label>
      <label><span>State</span><input value={filters.state} onChange={(e)=>update("state",e.target.value)} placeholder="TX" maxLength={2} /></label>
      <label className="checkbox-row"><input type="checkbox" checked={persist} onChange={(e)=>setPersist(e.target.checked)} /> Store returned records in ForgeGov</label>
      <button className="primary-button" disabled={loading}><Search size={17}/>{loading ? "Searching..." : "Search SAM.gov"}</button>
    </form><p className="helper-text">{message}</p></section>
    <section className="panel table-panel"><div className="panel-header"><div><span className="eyebrow">Results</span><h2>Federal opportunities</h2></div></div>
      {rows.length===0 ? <div className="empty-state"><Search size={28}/><strong>No results loaded</strong><p>Run a live search. ForgeGov does not fill this table with sample solicitations.</p></div> : <div className="table-wrap"><table><thead><tr><th>Opportunity</th><th>Agency</th><th>Codes</th><th>Posted</th><th>Deadline</th><th>Source</th></tr></thead><tbody>{rows.map((row,index)=><tr key={row.noticeId ?? `${row.solicitationNumber}-${index}`}><td><strong>{row.title ?? "Untitled notice"}</strong><span>{row.solicitationNumber ?? row.type ?? ""}</span></td><td>{row.fullParentPathName ?? "—"}<span>{row.setAside ?? ""}</span></td><td>NAICS {row.naicsCode ?? "—"}<span>PSC {row.classificationCode ?? "—"}</span></td><td>{row.postedDate ?? "—"}</td><td>{row.responseDeadLine ?? "—"}</td><td><a href={row.uiLink ?? `https://sam.gov/opp/${row.noticeId}/view`} target="_blank" rel="noreferrer">SAM.gov <ExternalLink size={14}/></a></td></tr>)}</tbody></table></div>}
    </section>
  </>;
}
