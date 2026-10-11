"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { Building2, Database, Handshake, Network, RefreshCw, Search, ShieldCheck, Users } from "lucide-react";
import { apiGet } from "@/lib/api";

type Row = Record<string, unknown>;
type Dossier = {
  identity: { id?: number | null; name: string; uei?: string; cage_code?: string; state?: string; socioeconomic_statuses?: string[] };
  metrics: { award_count: number; obligated_amount: number; potential_amount: number; agency_count: number; active_awards: number; latest_end?: string | null };
  top_agencies: Row[]; top_naics: Row[]; top_psc: Row[]; vehicles: Row[]; recent_awards: Row[];
  evidence: { classification: string; latest_source_update?: string | null; warning: string };
};
type AgencyPatterns = { agency: string; metrics: Row; fiscal_years: Row[]; top_vendors: Row[]; top_offices: Row[]; top_categories: Row[]; recent_opportunities: Row[]; evidence: Row };
type MarketMap = { category_type: string; code: string; categories: Row[]; vendors: Row[]; agencies: Row[]; relationships: Row[]; warning: string };
type VehicleAnalysis = { metrics: Row; holders: Row[]; agencies: Row[]; expiring: Row[]; recent: Row[]; evidence: Row };
type Teaming = { results: Array<{ organization_id: number; name: string; score: number; reasons: string[]; gaps: string[]; relationship_status: string; verified: boolean; state: string; href: string }>; warning: string };

const money = (value: unknown) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value || 0));
const text = (value: unknown, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);

export default function MarketIntelligencePage() {
  const [tab, setTab] = useState<"vendors"|"agency"|"map"|"vehicles"|"teaming">("vendors");
  const [query, setQuery] = useState("");
  const [compare, setCompare] = useState("");
  const [categoryType, setCategoryType] = useState("naics");
  const [code, setCode] = useState("");
  const [dossiers, setDossiers] = useState<Dossier[]>([]);
  const [agency, setAgency] = useState<AgencyPatterns | null>(null);
  const [map, setMap] = useState<MarketMap | null>(null);
  const [vehicles, setVehicles] = useState<VehicleAnalysis | null>(null);
  const [teaming, setTeaming] = useState<Teaming | null>(null);
  const [message, setMessage] = useState("Choose an intelligence view and run a search.");
  const [busy, setBusy] = useState(false);

  async function run(event?: FormEvent) {
    event?.preventDefault(); setBusy(true); setMessage("Analyzing stored official evidence…");
    try {
      if (tab === "vendors") {
        const names = compare.split("|").map(item => item.trim()).filter(Boolean);
        if (names.length >= 2) {
          const result = await apiGet<{vendors:Dossier[]}>(`/intelligence/market/vendors/compare/?vendors=${encodeURIComponent(names.slice(0,4).join("|"))}`);
          setDossiers(result.vendors); setMessage(`${result.vendors.length} vendors compared using the same stored evidence definitions.`);
        } else {
          const result = await apiGet<Dossier>(`/intelligence/market/vendors/dossier/?name=${encodeURIComponent(query)}`);
          setDossiers([result]); setMessage(result.evidence.warning);
        }
      } else if (tab === "agency") {
        const result = await apiGet<AgencyPatterns>(`/intelligence/market/agencies/patterns/?name=${encodeURIComponent(query)}`);
        setAgency(result); setMessage(text(result.evidence.warning));
      } else if (tab === "map") {
        const result = await apiGet<MarketMap>(`/intelligence/market/map/?type=${categoryType}&code=${encodeURIComponent(code)}`);
        setMap(result); setMessage(result.warning);
      } else if (tab === "vehicles") {
        const result = await apiGet<VehicleAnalysis>(`/intelligence/market/vehicles/?q=${encodeURIComponent(query)}`);
        setVehicles(result); setMessage(text(result.evidence.warning));
      } else {
        const params = new URLSearchParams(); if (code) params.set(categoryType, code); if (query.length === 2) params.set("state", query);
        const result = await apiGet<Teaming>(`/intelligence/market/teaming/?${params}`);
        setTeaming(result); setMessage(result.warning);
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : "Market intelligence request failed."); }
    finally { setBusy(false); }
  }

  const tabs = [
    ["vendors", "Competitors"], ["agency", "Agency patterns"], ["map", "Market map"], ["vehicles", "Vehicles"], ["teaming", "Teaming"],
  ] as const;
  return <div className="page-stack market-intelligence-page">
    <header className="page-hero"><div><span className="eyebrow">MARKET & COMPETITOR INTELLIGENCE 2.0</span><h1>Market Intelligence</h1><p>Compare competitors, understand agency buying history, inspect contract vehicles, map markets, and identify evidence-backed teaming candidates.</p></div><ShieldCheck size={34}/></header>
    <nav className="workspace-tabs" aria-label="Market intelligence views" role="tablist">{tabs.map(([key,label])=><button key={key} role="tab" aria-selected={tab===key} className={tab===key?"active":""} onClick={()=>setTab(key)}>{label}</button>)}</nav>
    <form className="data-panel advanced-filter-grid" onSubmit={run}>
      {tab !== "map" && <label><span>{tab==="agency"?"Agency":tab==="teaming"?"State (optional)":tab==="vehicles"?"Vehicle, holder, or agency":"Vendor name"}</span><input required={tab==="agency"||(tab==="vendors"&&!compare.trim())} value={query} onChange={event=>setQuery(event.target.value)} placeholder={tab==="agency"?"Department of the Army":tab==="teaming"?"TX":"Company or market term"}/></label>}
      {tab === "vendors" && <label><span>Compare 2–4 vendors (separate with |)</span><input value={compare} onChange={event=>setCompare(event.target.value)} placeholder="Vendor One | Vendor Two"/></label>}
      {(tab === "map" || tab === "teaming") && <><label><span>Category</span><select value={categoryType} onChange={event=>setCategoryType(event.target.value)}><option value="naics">NAICS</option><option value="psc">PSC</option></select></label><label><span>Code {tab==="teaming"?"(optional)":""}</span><input value={code} onChange={event=>setCode(event.target.value)} placeholder="541512"/></label></>}
      <button className="primary-button" disabled={busy}>{busy?<RefreshCw className="spin" size={16}/>:<Search size={16}/>} Analyze</button>
    </form>
    <p className="inline-message" role="status">{message}</p>

    {tab === "vendors" && <section className="market-comparison-grid">{dossiers.map(item=><article className="data-panel" key={`${item.identity.name}-${item.identity.uei}`}><div className="panel-title-row"><div><span className="eyebrow">COMPETITOR DOSSIER</span><h2>{item.identity.name||"No vendor found"}</h2></div><Users/></div><div className="profile-metrics"><div><span>Awards</span><strong>{item.metrics.award_count.toLocaleString()}</strong></div><div><span>Obligated</span><strong>{money(item.metrics.obligated_amount)}</strong></div><div><span>Agencies</span><strong>{item.metrics.agency_count}</strong></div></div><p>UEI {item.identity.uei||"unavailable"} · CAGE {item.identity.cage_code||"unavailable"}</p><h3>Top agencies</h3><div className="competitive-vendor-list">{item.top_agencies.slice(0,5).map((row,index)=><div key={index}><strong>{text(row.awarding_agency)}</strong><span>{money(row.obligated)} · {Number(row.award_count||0)} awards</span></div>)}</div><h3>Category strengths</h3><p>{item.top_naics.slice(0,5).map(row=>text(row.naics_code)).join(" · ")||"No NAICS evidence"}</p><small>{item.evidence.warning}</small></article>)}</section>}
    {tab === "agency" && agency && <><section className="insight-strip"><div><span>Awards</span><strong>{Number(agency.metrics.award_count||0).toLocaleString()}</strong></div><div><span>Obligated</span><strong>{money(agency.metrics.obligated_amount)}</strong></div><div><span>Vendors</span><strong>{Number(agency.metrics.vendor_count||0).toLocaleString()}</strong></div><div><span>Active opportunities</span><strong>{Number(agency.metrics.active_opportunities||0)}</strong></div></section><div className="split-intelligence"><section className="data-panel"><h2>Top historical vendors</h2><div className="intelligence-list">{agency.top_vendors.map((row,index)=><article key={index}><Building2/><div><Link href={`/participants/vendors/profile?name=${encodeURIComponent(text(row.recipient_name,""))}`}><strong>{text(row.recipient_name)}</strong></Link><p>{Number(row.award_count||0)} awards · {money(row.obligated)}</p></div></article>)}</div></section><section className="data-panel"><h2>Buying offices</h2><div className="competitive-vendor-list">{agency.top_offices.map((row,index)=><div key={index}><strong>{text(row.awarding_office)}</strong><span>{money(row.obligated)}</span></div>)}</div></section></div></>}
    {tab === "map" && map && <div className="split-intelligence"><section className="data-panel"><h2>Leading agencies</h2><div className="competitive-vendor-list">{map.agencies.map((row,index)=><div key={index}><strong>{text(row.awarding_agency)}</strong><span>{money(row.obligated)} · {Number(row.vendor_count||0)} vendors</span></div>)}</div></section><section className="data-panel"><h2>Leading vendors</h2><div className="competitive-vendor-list">{map.vendors.map((row,index)=><div key={index}><Link href={`/participants/vendors/profile?name=${encodeURIComponent(text(row.recipient_name,""))}`}><strong>{text(row.recipient_name)}</strong></Link><span>{money(row.obligated)}</span></div>)}</div></section></div>}
    {tab === "vehicles" && vehicles && <><section className="insight-strip"><div><span>Vehicles</span><strong>{Number(vehicles.metrics.vehicle_count||0).toLocaleString()}</strong></div><div><span>Obligated</span><strong>{money(vehicles.metrics.obligated_amount)}</strong></div><div><span>Potential ceiling</span><strong>{money(vehicles.metrics.potential_amount)}</strong></div></section><section className="data-panel"><h2>Leading vehicle holders</h2><div className="intelligence-list">{vehicles.holders.map((row,index)=><article key={index}><Network/><div><Link href={`/participants/vendors/profile?name=${encodeURIComponent(text(row.recipient_name,""))}`}><strong>{text(row.recipient_name)}</strong></Link><p>{Number(row.vehicle_count||0)} vehicles · {money(row.obligated)} obligated · {money(row.potential)} potential</p><small>Latest recorded end {text(row.latest_end)}</small></div></article>)}</div></section></>}
    {tab === "teaming" && teaming && <section className="data-panel"><h2>Recommended partners</h2><div className="intelligence-list">{teaming.results.map(row=><article key={row.organization_id}><Handshake/><div><Link href={row.href}><strong>{row.name}</strong></Link><p>{row.reasons.join(" · ")}</p><small>{row.score}% evidence fit · relationship {row.relationship_status}{row.gaps.length?` · verify: ${row.gaps.join(", ")}`:""}</small></div></article>)}</div></section>}
    {!dossiers.length && tab === "vendors" && <div className="table-state"><Database/><strong>Search for a vendor or compare competitors</strong><p>ForgeGov will use stored official award evidence and keep private CRM contacts inside your workspace.</p></div>}
  </div>;
}
