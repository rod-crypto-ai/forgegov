"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Bell, Building2, Database, ExternalLink, Landmark, Network, RefreshCw, Search, Target, Users } from "lucide-react";
import { apiGet, apiPatch, apiPost, normalizeList } from "@/lib/api";

type Row = Record<string, unknown>;

function deferredLoad(load: () => void | Promise<void>) {
  const timer = window.setTimeout(() => void load(), 0);
  return () => window.clearTimeout(timer);
}

function useInitialLoad(load: () => void | Promise<void>) {
  const initialLoad = useRef(load);
  useEffect(() => deferredLoad(() => initialLoad.current()), []);
}

function money(value: unknown) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value ?? 0));
}

function text(value: unknown, fallback = "—") {
  if (value === null || value === undefined || value === "") return fallback;
  return String(value);
}

function firstText(...values: unknown[]) {
  for (const value of values) {
    if (value !== null && value !== undefined && value !== "") return String(value);
  }
  return "—";
}

export function ForecastWorkspace() {
  const [query, setQuery] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [status, setStatus] = useState("Loading official forecast sources…");
  const load = useCallback(async () => {
    setStatus("Refreshing Acquisition.gov forecast sources…");
    try {
      const data = await apiGet<{ results: Row[]; reachable: boolean }>(`/intelligence/forecasts/sources/?q=${encodeURIComponent(query)}`);
      setRows(data.results ?? []);
      setStatus(`${data.results?.length ?? 0} official agency forecast sources loaded${data.reachable ? "" : " from the fallback directory"}.`);
    } catch (error) { setStatus(error instanceof Error ? error.message : "Forecast source request failed"); }
  }, [query]);
  useInitialLoad(load);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">Forward-looking acquisition intelligence</span><h1>Federal Procurement Forecasts</h1><p>Search the official Acquisition.gov directory and open each agency’s current procurement forecast.</p></div></header>
    <section className="data-panel"><form className="quick-create-form" onSubmit={(event) => { event.preventDefault(); void load(); }}><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Department of Defense, VA, DHS…"/><button className="primary-button"><Search size={16}/> Search forecasts</button></form><p className="inline-message">{status}</p></section>
    <section className="source-card-grid">{rows.map((row, index) => <article className="source-card" key={`${text(row.agency)}-${index}`}><Landmark/><div><span>Agency forecast</span><h3>{text(row.agency)}</h3><p>Official recurring procurement forecast source.</p></div><a className="primary-button" href={text(row.forecast_url)} target="_blank" rel="noreferrer">Open forecast <ExternalLink size={15}/></a></article>)}</section>
  </>;
}

export function StateLocalWorkspace() {
  const [query, setQuery] = useState("");
  const [state, setState] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [message, setMessage] = useState("Loading official state procurement portals…");
  const load = useCallback(async () => {
    const params = new URLSearchParams(); if (query) params.set("q", query); if (state) params.set("state", state);
    try { const data = await apiGet<{ results: Row[] }>(`/intelligence/state-local/sources/?${params}`); setRows(data.results ?? []); setMessage(`${data.results?.length ?? 0} official procurement sources loaded.`); }
    catch (error) { setMessage(error instanceof Error ? error.message : "State/local source request failed"); }
  }, [query, state]);
  useInitialLoad(load);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">State and local market access</span><h1>State & Local Procurement Sources</h1><p>Open verified public procurement portals while ForgeGov’s source-specific adapters are expanded.</p></div></header>
    <section className="data-panel"><form className="advanced-filter-grid" onSubmit={(e) => {e.preventDefault();void load();}}><label><span>Keyword</span><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="California, construction…"/></label><label><span>State code</span><input value={state} onChange={(e)=>setState(e.target.value.toUpperCase())} maxLength={2} placeholder="TX"/></label><button className="primary-button"><Search size={16}/> Find sources</button></form><p className="inline-message">{message}</p></section>
    <section className="source-card-grid">{rows.map((row, index)=><article className="source-card" key={`${text(row.state)}-${index}`}><Building2/><div><span>{text(row.state)}</span><h3>{text(row.jurisdiction)}</h3><p>{text(row.coverage)}</p></div><a className="primary-button" href={text(row.portal)} target="_blank" rel="noreferrer">Open portal <ExternalLink size={15}/></a></article>)}</section>
  </>;
}

type VehicleResult = { results: Row[]; page_metadata?: { hasNext?: boolean; total?: number }; persisted?: { created?: number; updated?: number } };
export function ContractVehicleWorkspace() {
  const [query, setQuery] = useState(""); const [agency, setAgency] = useState(""); const [recipient, setRecipient] = useState(""); const [page, setPage] = useState(1); const [data, setData] = useState<VehicleResult>({results:[]}); const [message,setMessage]=useState("Loading federal contract vehicles…");
  const search = useCallback(async (requestedPage = 1) => {
    setMessage("Searching USAspending IDV records…"); const params=new URLSearchParams({page:String(requestedPage),limit:"50",persist:"true"}); if(query)params.set("q",query);if(agency)params.set("agency",agency);if(recipient)params.set("recipient",recipient);
    try{const result=await apiGet<VehicleResult>(`/live/usaspending/vehicles/?${params}`);setData(result);setPage(requestedPage);setMessage(`${result.results?.length??0} contract vehicles loaded.`);}catch(error){setMessage(error instanceof Error?error.message:"Vehicle search failed");}
  },[agency,query,recipient]);
  useInitialLoad(() => search(1));
  const potential=useMemo(()=>data.results.reduce((sum,row)=>sum+Number(row["Potential Award Amount"]??row["Award Amount"]??0),0),[data.results]);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">IDIQ, BPA and contract vehicle intelligence</span><h1>Federal Contract Vehicles</h1><p>Search live USAspending IDV records, identify vehicle holders, and persist results for competitor analysis.</p></div></header>
    <section className="insight-strip"><div><span>Loaded</span><strong>{data.results.length}</strong></div><div><span>Potential value</span><strong>{money(potential)}</strong></div><div><span>Page</span><strong>{page}</strong></div><div><span>Source</span><strong>USAspending</strong></div></section>
    <section className="data-panel"><form className="advanced-filter-grid" onSubmit={(e)=>{e.preventDefault();void search(1);}}><label><span>Keyword</span><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="logistics, IT, maintenance"/></label><label><span>Awarding agency</span><input value={agency} onChange={(e)=>setAgency(e.target.value)} placeholder="Department of Defense"/></label><label><span>Vehicle holder</span><input value={recipient} onChange={(e)=>setRecipient(e.target.value)} placeholder="Company name"/></label><button className="primary-button"><Search size={16}/> Search vehicles</button></form><p className="inline-message">{message}</p></section>
    <section className="data-panel"><div className="intelligence-list">{data.results.map((row,index)=><article key={`${text(row.generated_unique_award_id)}-${index}`}><Network/><div><span>{text(row["Award Type"])}</span><h3>{text(row["Award ID"])}</h3><p>{text(row.Description)}</p><small>{text(row["Awarding Agency"])} · {text(row["Recipient Name"])} · {money(row["Potential Award Amount"]??row["Award Amount"])}</small></div>{row.generated_unique_award_id?<a href={`https://www.usaspending.gov/award/${text(row.generated_unique_award_id)}/`} target="_blank" rel="noreferrer"><ExternalLink size={17}/></a>:null}</article>)}</div><div className="pagination-bar"><button className="secondary-button" disabled={page<=1} onClick={()=>void search(page-1)}>Previous</button><span>Page {page}</span><button className="secondary-button" disabled={!data.page_metadata?.hasNext} onClick={()=>void search(page+1)}>Next</button></div></section>
  </>;
}

export function SubcontractWorkspace() {
  const [query,setQuery]=useState("");const[state,setState]=useState("");const[idv,setIdv]=useState("");const[subnet,setSubnet]=useState<Row[]>([]);const[subawards,setSubawards]=useState<Row[]>([]);const[message,setMessage]=useState("Loading subcontract intelligence…");
  const load = useCallback(async()=>{setMessage("Checking SBA SUBNet and SAM subaward reporting…");try{const [a,b]=await Promise.all([apiGet<{results:Row[]}>(`/live/sba/subnet/?q=${encodeURIComponent(query)}&state=${encodeURIComponent(state)}`),apiGet<{results:Row[]}>(`/live/sam/subawards/?referenced_idv=${encodeURIComponent(idv)}&limit=50`)]);setSubnet(a.results??[]);setSubawards(b.results??[]);setMessage(`${a.results?.length??0} live SUBNet opportunities and ${b.results?.length??0} reported subawards loaded.`);}catch(error){setMessage(error instanceof Error?error.message:"Subcontract intelligence failed");}},[idv,query,state]);
  useInitialLoad(load);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">Prime and subcontract intelligence</span><h1>Subcontracting</h1><p>Combine current SBA SUBNet postings with SAM.gov acquisition subaward reporting.</p></div></header>
    <section className="data-panel"><form className="advanced-filter-grid" onSubmit={(e)=>{e.preventDefault();void load();}}><label><span>SUBNet keyword</span><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="mowing, HVAC, logistics"/></label><label><span>State</span><input value={state} onChange={(e)=>setState(e.target.value)} placeholder="Texas"/></label><label><span>Referenced IDV PIID</span><input value={idv} onChange={(e)=>setIdv(e.target.value)} placeholder="W52P1J18DA075"/></label><button className="primary-button"><RefreshCw size={16}/> Refresh intelligence</button></form><p className="inline-message">{message}</p></section>
    <div className="split-intelligence"><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CURRENT OPPORTUNITIES</span><h2>SBA SUBNet</h2></div></div><div className="intelligence-list">{subnet.map((row,index)=><article key={`${text(row.title)}-${index}`}><Target/><div><h3>{text(row.title)}</h3><p>{text(row.place_of_performance)} · NAICS {text(row.naics)}</p><small>Closes {text(row.closing_date)} · {text(row.point_of_contact)}</small></div><a href={text(row.source_url)} target="_blank" rel="noreferrer"><ExternalLink size={17}/></a></article>)}</div></section><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">REPORTED PERFORMANCE</span><h2>SAM Subawards</h2></div></div><div className="intelligence-list">{subawards.map((row,index)=><article key={`${text(row.piid)}-${index}`}><Database/><div><h3>{text(row.subcontractor)||"Reported subcontractor"}</h3><p>{text(row.description)}</p><small>{text(row.prime_contractor)} · {money(row.amount)} · PIID {text(row.piid)}</small></div></article>)}</div></section></div>
  </>;
}

type PartnerRow={id:number;name:string;uei?:string;cage_code?:string;city?:string;state?:string;website?:string;socioeconomic_statuses?:string[];naics_codes?:string[];award_count?:number;obligated_amount?:number;top_agencies?:Row[]};
type TeamingRequestRow={id:number;company_name:string;role:string;status:string;capabilities?:string};
export function TeamingWorkspace(){
  const[query,setQuery]=useState("");const[naics,setNaics]=useState("");const[state,setState]=useState("");const[status,setStatus]=useState("");const[partners,setPartners]=useState<PartnerRow[]>([]);const[requests,setRequests]=useState<TeamingRequestRow[]>([]);const[message,setMessage]=useState("Search stored vendor and award intelligence for teaming candidates.");
  const loadRequests=useCallback(async()=>{const data=await apiGet<TeamingRequestRow[]|{results:TeamingRequestRow[]}>("/teaming-requests/?page_size=100");setRequests(normalizeList<TeamingRequestRow>(data));},[]);
  useInitialLoad(loadRequests);
  async function searchPartners(){const params=new URLSearchParams();if(query)params.set("q",query);if(naics)params.set("naics",naics);if(state)params.set("state",state);if(status)params.set("status",status);setMessage("Analyzing vendors and award history…");try{const data=await apiGet<{results:PartnerRow[]}>(`/intelligence/partners/?${params}`);setPartners(data.results??[]);setMessage(`${data.results?.length??0} potential teaming partners loaded.`);}catch(error){setMessage(error instanceof Error?error.message:"Partner discovery failed");}}
  async function createLead(partner:PartnerRow){try{await apiPost("/teaming-requests/",{company_name:partner.name,role:"subcontractor",status:"draft",capabilities:[...(partner.naics_codes??[]),...(partner.socioeconomic_statuses??[])].join(", ")});setMessage(`${partner.name} added as a draft teaming lead.`);await loadRequests();}catch(error){setMessage(error instanceof Error?error.message:"Teaming lead could not be created");}}
  return <>
    <header className="feature-hero"><div><span className="eyebrow">Partner intelligence and outreach pipeline</span><h1>Teaming Partner Discovery</h1><p>Find candidates using stored vendor profiles, NAICS coverage, socioeconomic indicators, and federal award history.</p></div></header>
    <section className="data-panel"><form className="advanced-filter-grid" onSubmit={(e)=>{e.preventDefault();void searchPartners();}}><label><span>Company / UEI / CAGE</span><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="Company name"/></label><label><span>NAICS</span><input value={naics} onChange={(e)=>setNaics(e.target.value)} placeholder="811310"/></label><label><span>State</span><input value={state} onChange={(e)=>setState(e.target.value.toUpperCase())} maxLength={2} placeholder="TX"/></label><label><span>Socioeconomic status</span><input value={status} onChange={(e)=>setStatus(e.target.value)} placeholder="SDVOSB, HUBZone…"/></label><button className="primary-button"><Search size={16}/> Find partners</button></form><p className="inline-message">{message}</p></section>
    <div className="split-intelligence"><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">DISCOVERY</span><h2>Potential partners</h2></div><small>{partners.length} matches</small></div><div className="intelligence-list">{partners.map((partner)=><article key={partner.id}><Users/><div><span>{firstText(partner.uei,partner.cage_code)}</span><h3>{partner.name}</h3><p>{text(partner.city,"")}{partner.city&&partner.state?", ":""}{text(partner.state,"")} · {Number(partner.award_count??0).toLocaleString()} awards · {money(partner.obligated_amount)}</p><small>{[...(partner.socioeconomic_statuses??[]),...(partner.naics_codes??[])].slice(0,8).join(" · ")||"Profile indicators unavailable"}</small></div><button className="secondary-button" onClick={()=>void createLead(partner)}>Add lead</button></article>)}</div></section><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">WORKSPACE</span><h2>Teaming leads</h2></div><small>{requests.length} records</small></div><div className="intelligence-list">{requests.map((request)=><article key={request.id}><Target/><div><span>{request.status} · {request.role}</span><h3>{request.company_name}</h3><p>{request.capabilities||"No capability notes yet."}</p></div></article>)}</div></section></div>
  </>;
}

export function ProfileWorkspace({kind}:{kind:"agency"|"vendor"}){
  const[query,setQuery]=useState("");const[rows,setRows]=useState<Row[]>([]);const[message,setMessage]=useState(`Search ${kind} intelligence.`);
  const load=useCallback(async()=>{try{const data=await apiGet<{results:Row[]}>(`/intelligence/${kind==="agency"?"agencies":"vendors"}/?q=${encodeURIComponent(query)}`);setRows(data.results??[]);setMessage(`${data.results?.length??0} profiles loaded from stored award intelligence.`);}catch(error){setMessage(error instanceof Error?error.message:"Profile search failed");}},[kind,query]);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">{kind==="agency"?"Buyer intelligence":"Competitor intelligence"}</span><h1>{kind==="agency"?"Federal Agency Profiles":"Vendor & Competitor Profiles"}</h1><p>{kind==="agency"?"Analyze agency spending, active opportunities, leading vendors, and category concentration.":"Analyze award history, agency relationships, category strengths, and recent wins."}</p></div></header>
    <section className="data-panel"><form className="quick-create-form" onSubmit={(e)=>{e.preventDefault();void load();}}><input value={query} onChange={(e)=>setQuery(e.target.value)} placeholder={kind==="agency"?"Department of the Navy":"Company name, UEI or CAGE"}/><button className="primary-button"><Search size={16}/> Search profiles</button></form><p className="inline-message">{message}</p></section>
    <section className="profile-grid">{rows.map((row,index)=><article className="profile-card" key={`${text(row.id)}-${index}`}><header>{kind==="agency"?<Building2/>:<Users/>}<div><span>{kind==="agency"?text(row.agency_code):firstText(row.uei, row.cage_code)}</span><h3>{text(row.name)}</h3></div></header><div className="profile-metrics"><div><span>Awards</span><strong>{Number(row.award_count??0).toLocaleString()}</strong></div><div><span>Obligated</span><strong>{money(row.obligated_amount)}</strong></div>{kind==="agency"?<div><span>Active opportunities</span><strong>{Number(row.active_opportunities??0).toLocaleString()}</strong></div>:null}</div><h4>{kind==="agency"?"Top vendors":"Top agencies"}</h4><ul>{((kind==="agency"?row.top_vendors:row.top_agencies) as Row[]|undefined)?.map((item,i)=><li key={i}><span>{text(item.recipient_name??item.awarding_agency)}</span><b>{money(item.obligated)}</b></li>)}</ul></article>)}</section>
  </>;
}

export function MarketAnalyticsWorkspace({categoryType}:{categoryType:"naics"|"psc"}){
  const[rows,setRows]=useState<Row[]>([]);const[message,setMessage]=useState("Loading stored market intelligence…");
  const load=useCallback(async()=>{try{const data=await apiGet<{results:Row[]}>(`/intelligence/categories/?type=${categoryType}`);setRows(data.results??[]);setMessage(`${data.results?.length??0} ${categoryType.toUpperCase()} markets analyzed.`);}catch(error){setMessage(error instanceof Error?error.message:"Market analytics failed");}},[categoryType]);
  useInitialLoad(load);
  return <>
    <header className="feature-hero"><div><span className="eyebrow">Category intelligence</span><h1>{categoryType.toUpperCase()} Market Analytics</h1><p>Compare obligated dollars, award volume, vendor concentration, agency demand, and active opportunity counts.</p></div><button className="secondary-button" onClick={()=>void load()}><RefreshCw size={16}/> Refresh</button></header><p className="inline-message">{message}</p>
    <section className="data-panel"><div className="market-table"><div className="market-row market-head"><b>Code</b><b>Obligated</b><b>Awards</b><b>Vendors</b><b>Agencies</b><b>Opportunities</b></div>{rows.map((row,index)=><div className="market-row" key={`${text(row.code)}-${index}`}><strong>{text(row.code)}</strong><span>{money(row.obligated)}</span><span>{Number(row.award_count??0).toLocaleString()}</span><span>{Number(row.vendor_count??0).toLocaleString()}</span><span>{Number(row.agency_count??0).toLocaleString()}</span><span>{Number(row.opportunity_count??0).toLocaleString()}</span></div>)}</div></section>
  </>;
}

type AlertRow={id:number;title:string;summary?:string;source_url?:string;created_at:string;read:boolean;dismissed:boolean;alert_type:string};
export function AlertsWorkspace(){
  const[rows,setRows]=useState<AlertRow[]>([]);const[message,setMessage]=useState("Loading opportunity alerts…");
  const load=useCallback(async()=>{try{const data=await apiGet<AlertRow[]|{results:AlertRow[]}>("/alerts/?dismissed=false&page_size=250");const alerts=normalizeList<AlertRow>(data);setRows(alerts);setMessage(`${alerts.filter((row)=>!row.read).length} unread alerts.`);}catch(error){setMessage(error instanceof Error?error.message:"Alerts could not be loaded");}},[]);
  useInitialLoad(load);
  async function evaluate(){setMessage("Evaluating saved searches against live SAM.gov data…");try{const result=await apiPost<{alerts_created:number;saved_searches_evaluated:number}>("/workflow/saved-searches/evaluate/",{});setMessage(`${result.saved_searches_evaluated} saved searches evaluated; ${result.alerts_created} new alerts created.`);await load();}catch(error){setMessage(error instanceof Error?error.message:"Alert evaluation failed");}}
  async function patch(id:number,payload:Partial<AlertRow>){await apiPatch(`/alerts/${id}/`,payload);await load();}
  return <>
    <header className="feature-hero"><div><span className="eyebrow">Automated opportunity monitoring</span><h1>Alerts</h1><p>Run saved searches against live SAM.gov data and review new matches in one inbox.</p></div><button className="primary-button" onClick={()=>void evaluate()}><RefreshCw size={16}/> Evaluate now</button></header><p className="inline-message">{message}</p>
    <section className="data-panel"><div className="intelligence-list">{rows.map(row=><article className={row.read?"alert-read":""} key={row.id}><Bell/><div><span>{row.alert_type.replaceAll("_"," ")}</span><h3>{row.title}</h3><p>{row.summary||"Matched a saved search."}</p><small>{new Date(row.created_at).toLocaleString()}</small></div><div className="alert-actions">{row.source_url?<a href={row.source_url} target="_blank" rel="noreferrer"><ExternalLink size={17}/></a>:null}<button className="secondary-button" onClick={()=>void patch(row.id,{read:!row.read})}>{row.read?"Unread":"Read"}</button><button className="secondary-button" onClick={()=>void patch(row.id,{dismissed:true})}>Dismiss</button></div></article>)}</div></section>
  </>;
}
