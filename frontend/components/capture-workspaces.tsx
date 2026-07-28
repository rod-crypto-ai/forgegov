"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import { apiDelete, apiGet, apiPatch, apiPost, normalizeList } from "@/lib/api";

type Opportunity = { id:number; title:string; agency?:string; solicitation_number?:string; response_deadline?:string; source_url?:string };
type Pipeline = { id:number; stage:string; probability_of_win:number; estimated_value?:string; next_action?:string; notes?:string; opportunity_detail:Opportunity };
type Pursuit = { id:number; title:string; stage:string; probability_of_win:number; estimated_value?:string; due_date?:string; next_action?:string; incumbent?:string };
type Task = { id:number; title:string; description?:string; due_at?:string; completed:boolean; pipeline_item?:number };
type SavedSearch = { id:number; name:string; filters:Record<string,string>; alert_frequency:string; enabled:boolean };
const stages=["discovered","reviewing","qualified","bid_decision","capture","teaming","proposal","submitted","awarded","lost","no_bid"];
const human=(v:string)=>v.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const money=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0});

export function PipelineWorkspace(){
 const [rows,setRows]=useState<Pipeline[]>([]); const [error,setError]=useState(""); const [loading,setLoading]=useState(true);
 const load=useCallback(async()=>{setLoading(true);try{setRows(normalizeList(await apiGet<Pipeline[]>("/pipeline/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load pipeline")}finally{setLoading(false)}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function update(id:number,payload:Record<string,unknown>){try{await apiPatch(`/pipeline/${id}/`,payload);await load()}catch(e){setError(e instanceof Error?e.message:"Update failed")}}
 async function pursue(id:number){try{await apiPost(`/workflow/pipeline/${id}/create-pursuit/`,{});await load();setError("Pursuit created and linked.")}catch(e){setError(e instanceof Error?e.message:"Could not create pursuit")}}
 const total=useMemo(()=>rows.reduce((s,r)=>s+Number(r.estimated_value??0),0),[rows]);
 return <><header className="module-header"><div><span className="eyebrow">Capture operations</span><h1>Pipeline</h1><p>Qualify opportunities, advance capture stages, and convert selected work into managed pursuits.</p></div><button className="secondary-button" onClick={load}><RefreshCw size={16}/> Refresh</button></header>
 <section className="workspace-summary"><div><span>Pipeline items</span><strong>{rows.length}</strong><small>Live database records</small></div><div><span>Estimated value</span><strong>{money.format(total)}</strong><small>Across valued opportunities</small></div><div><span>In capture</span><strong>{rows.filter(r=>["capture","teaming","proposal"].includes(r.stage)).length}</strong><small>Active capture work</small></div><div><span>Submitted</span><strong>{rows.filter(r=>r.stage==="submitted").length}</strong><small>Awaiting decision</small></div></section>
 {error&&<div className="system-banner warning">{error}</div>}
 <section className="data-panel">{loading?<div className="table-state"><RefreshCw className="spin"/><strong>Loading pipeline</strong></div>:!rows.length?<div className="table-state"><strong>No pipeline items yet</strong><p>Search federal opportunities and use Add to pipeline.</p></div>:<div className="pipeline-list">{rows.map(r=><article className="pipeline-row" key={r.id}><div><span className="eyebrow">{r.opportunity_detail.solicitation_number||"Federal opportunity"}</span><h3>{r.opportunity_detail.title}</h3><p>{r.opportunity_detail.agency||"Agency unavailable"}</p></div><label><span>Stage</span><select value={r.stage} onChange={e=>void update(r.id,{stage:e.target.value})}>{stages.map(s=><option key={s} value={s}>{human(s)}</option>)}</select></label><label><span>Win probability</span><input type="number" min="0" max="100" value={r.probability_of_win} onChange={e=>void update(r.id,{probability_of_win:Number(e.target.value)})}/></label><label><span>Next action</span><input value={r.next_action??""} onBlur={e=>void update(r.id,{next_action:e.target.value})} onChange={e=>setRows(x=>x.map(a=>a.id===r.id?{...a,next_action:e.target.value}:a))}/></label><button className="primary-button" onClick={()=>void pursue(r.id)}>Create pursuit <ChevronRight size={15}/></button></article>)}</div>}</section></>;
}

export function PursuitsWorkspace(){
 const [rows,setRows]=useState<Pursuit[]>([]);const [error,setError]=useState("");
 const load=useCallback(async()=>{try{setRows(normalizeList(await apiGet<Pursuit[]>("/pursuits/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load pursuits")}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function patch(id:number,payload:Record<string,unknown>){try{await apiPatch(`/pursuits/${id}/`,payload);await load()}catch(e){setError(e instanceof Error?e.message:"Update failed")}}
 return <><header className="module-header"><div><span className="eyebrow">Capture management</span><h1>Pursuits</h1><p>Manage qualified opportunities from capture planning through proposal submission and award.</p></div><button className="secondary-button" onClick={load}><RefreshCw size={16}/> Refresh</button></header>{error&&<div className="system-banner warning">{error}</div>}<section className="data-panel"><div className="kanban-board">{["triage","qualify","bid_decision","capture","proposal","submitted","awarded"].map(stage=><section className="kanban-column" key={stage}><header><span>{human(stage)}</span><b>{rows.filter(r=>r.stage===stage).length}</b></header>{rows.filter(r=>r.stage===stage).map(r=><article className="kanban-card" key={r.id}><strong>{r.title}</strong><p>{r.next_action||"No next action set"}</p><label><span>Move to</span><select value={r.stage} onChange={e=>void patch(r.id,{stage:e.target.value})}>{["triage","qualify","bid_decision","capture","proposal","submitted","awarded","lost","no_bid"].map(s=><option key={s} value={s}>{human(s)}</option>)}</select></label><label><span>Win probability</span><input type="number" min="0" max="100" value={r.probability_of_win} onChange={e=>void patch(r.id,{probability_of_win:Number(e.target.value)})}/></label></article>)}</section>)}</div></section></>;
}

export function TasksWorkspace(){
 const [rows,setRows]=useState<Task[]>([]);const [title,setTitle]=useState("");const [due,setDue]=useState("");const [error,setError]=useState("");
 const load=useCallback(async()=>{try{setRows(normalizeList(await apiGet<Task[]>("/tasks/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load tasks")}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function create(e:FormEvent){e.preventDefault();try{await apiPost("/workflow/tasks/",{title,due_at:due||null});setTitle("");setDue("");await load()}catch(e){setError(e instanceof Error?e.message:"Could not create task")}}
 async function toggle(t:Task){await apiPatch(`/tasks/${t.id}/`,{completed:!t.completed});await load()}
 async function remove(id:number){await apiDelete(`/tasks/${id}/`);await load()}
 return <><header className="module-header"><div><span className="eyebrow">Execution management</span><h1>Tasks</h1><p>Create, complete, and track capture work with due dates and pipeline relationships.</p></div></header><section className="data-panel"><form className="quick-create-form" onSubmit={create}><input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Add a task…" required/><input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)}/><button className="primary-button"><Plus size={16}/> Add task</button></form>{error&&<div className="form-error">{error}</div>}<div className="task-list">{rows.map(t=><article className={`task-row ${t.completed?"complete":""}`} key={t.id}><button className="icon-button" onClick={()=>void toggle(t)}>{t.completed?<CheckCircle2/>:<Circle/>}</button><div><strong>{t.title}</strong><span>{t.due_at?new Date(t.due_at).toLocaleString():"No due date"}</span></div><button className="icon-button" onClick={()=>void remove(t.id)}><Trash2 size={17}/></button></article>)}</div></section></>;
}

export function SavedSearchesWorkspace(){
 const [rows,setRows]=useState<SavedSearch[]>([]);const [error,setError]=useState("");
 const load=useCallback(async()=>{try{setRows(normalizeList(await apiGet<SavedSearch[]>("/saved-searches/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load searches")}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function remove(id:number){await apiDelete(`/saved-searches/${id}/`);await load()}
 return <><header className="module-header"><div><span className="eyebrow">Opportunity monitoring</span><h1>Saved Searches</h1><p>Reuse live SAM.gov filters and maintain searches that feed future alerts.</p></div><button className="secondary-button" onClick={load}><RefreshCw size={16}/> Refresh</button></header>{error&&<div className="system-banner warning">{error}</div>}<section className="data-panel"><div className="saved-search-grid">{rows.map(r=>{const {source,...searchFilters}=r.filters;const q=new URLSearchParams(searchFilters).toString();const route=source==="grants.gov"?"/opportunities/federal-grants":"/opportunities/federal-contracts";return <article className="saved-search-card" key={r.id}><div><Save size={18}/><span>{r.alert_frequency}</span></div><h3>{r.name}</h3><p>{Object.entries(r.filters).filter(([,v])=>v).map(([k,v])=>`${human(k)}: ${v}`).join(" · ")||"No filters"}</p><footer><a className="primary-button" href={`${route}?${q}`}>Run search</a><button className="icon-button" onClick={()=>void remove(r.id)}><Trash2 size={17}/></button></footer></article>})}</div></section></>;
}
