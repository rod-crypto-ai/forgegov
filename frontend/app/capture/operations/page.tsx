"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BarChart3, CheckCircle2, Circle, ClipboardCheck, RefreshCw, ShieldCheck, Target, Users } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Milestone={id:number;title:string;category:string;required:boolean;completed_at?:string|null;blocked:boolean;owner_name:string};
type Plan={id:number;status:string;template_key:string;objective:string;customer_need:string;win_strategy:string;key_risks:string[];progress_percent:number;milestones:Milestone[]};
type Pursuit={id:number;title:string;stage:string;owner_name:string;estimated_value:string|number;probability_of_win:number;weighted_value:string|number;due_date?:string|null;next_action:string;age_days:number;stale_days:number;agency:string;plan?:Plan|null;gate_findings:string[];allowed_transitions:string[]};
type Operations={
 definitions:Record<string,string>;
 summary:{active_pursuits:number;pipeline_value:string|number;weighted_pipeline:string|number;overdue:number;due_within_14_days:number;stale:number;unassigned:number;unlinked_pipeline_items:number};
 pursuits:Pursuit[];
 review_queue:Array<{pursuit_id:number;title:string;urgency:number;signals:string[]}>;
 workload:Array<{owner_id?:number|null;owner_name:string;pursuits:number;open_tasks:number;overdue_tasks:number}>;
 agency_concentration:Array<{agency:string;value:string|number;share_percent:number}>;
 weekly_review:{id?:number|null;week_start:string;status:string;notes:string;decisions:string[]};
 recent_changes:Array<{id:number;title:string;previous_stage:string;new_stage:string;previous_probability:number;new_probability:number;reason:string;changed_by:string;created_at:string}>;
 templates:Array<{key:string;name:string;milestone_count:number}>;
};

const money=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0});
const human=(value:string)=>value.replaceAll("_"," ").replace(/\b\w/g,char=>char.toUpperCase());

export default function CaptureOperationsPage(){
 const[data,setData]=useState<Operations|null>(null);const[message,setMessage]=useState("");const[busy,setBusy]=useState(false);const[notes,setNotes]=useState("");
 const load=useCallback(async()=>{setBusy(true);try{const result=await apiGet<Operations>("/capture/operations/");setData(result);setNotes(result.weekly_review.notes);setMessage("")}catch(error){setMessage(error instanceof Error?error.message:"Capture operations could not be loaded.")}finally{setBusy(false)}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function mutate(payload:Record<string,unknown>,success:string){setBusy(true);try{const result=await apiPost<Operations>("/capture/operations/",payload);setData(result);setNotes(result.weekly_review.notes);setMessage(success)}catch(error){setMessage(error instanceof Error?error.message:"The capture operation could not be completed.")}finally{setBusy(false)}}
 if(!data)return <main className="capture-ops-page"><header className="module-header"><div><span className="eyebrow">CAPTURE OPERATIONS</span><h1>Capture Operations & Pipeline</h1><p>Loading the organization-scoped operating picture…</p></div></header>{message&&<div className="system-banner warning">{message}</div>}</main>;
 const s=data.summary;
 return <main className="capture-ops-page">
  <header className="module-header"><div><span className="eyebrow">CAPTURE OPERATIONS</span><h1>Capture Operations & Pipeline</h1><p>Run accountable capture plans, governed stage transitions, weekly reviews, and one consistently defined pursuit portfolio.</p></div><button className="secondary-button" disabled={busy} onClick={()=>void load()}><RefreshCw className={busy?"spin":""} size={16}/> Refresh</button></header>
  {message&&<div className="system-banner">{message}</div>}
  <section className="capture-ops-summary">
   <article><Target/><span>Active pursuits</span><strong>{s.active_pursuits}</strong><small>{data.definitions.active_pursuit}</small></article>
   <article><BarChart3/><span>Pipeline value</span><strong>{money.format(Number(s.pipeline_value||0))}</strong><small>Canonical active-pursuit total</small></article>
   <article><ShieldCheck/><span>Weighted pipeline</span><strong>{money.format(Number(s.weighted_pipeline||0))}</strong><small>Entered value × probability</small></article>
   <article className={s.overdue?"risk":""}><AlertTriangle/><span>Overdue</span><strong>{s.overdue}</strong><small>Separate from {s.due_within_14_days} due within 14 days</small></article>
   <article className={s.stale||s.unassigned?"warning":""}><Users/><span>Accountability gaps</span><strong>{s.stale+s.unassigned}</strong><small>{s.stale} stale · {s.unassigned} unassigned</small></article>
  </section>

  <section className="capture-ops-grid">
   <article className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">WEEKLY REVIEW QUEUE</span><h2>Actions needing attention</h2></div><small>{data.review_queue.length} flagged</small></div><div className="capture-review-list">{data.review_queue.length?data.review_queue.map(row=><div key={row.pursuit_id}><AlertTriangle size={17}/><div><strong>{row.title}</strong><p>{row.signals.join(" · ")}</p></div><b>{row.urgency}</b></div>):<div className="table-state compact-state"><CheckCircle2/><strong>No current review signals</strong><p>Deadlines, ownership, next actions, and aging are under control.</p></div>}</div></article>
   <article className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">OWNER CAPACITY</span><h2>Workload and overdue work</h2></div></div><div className="capture-workload">{data.workload.map(row=><div key={row.owner_id??"none"}><strong>{row.owner_name}</strong><span>{row.pursuits} pursuits</span><span>{row.open_tasks} open tasks</span><b className={row.overdue_tasks?"risk-text":""}>{row.overdue_tasks} overdue</b></div>)}</div></article>
  </section>

  <section className="data-panel capture-plan-board"><div className="panel-title-row"><div><span className="eyebrow">CAPTURE PLANS & STAGE GATES</span><h2>Active pursuit execution</h2><p>Templates are additive. Existing pursuits, tasks, pricing, and opportunity workspaces remain intact.</p></div><small>{s.unlinked_pipeline_items} pipeline item(s) not yet converted to pursuits</small></div>
   <div className="capture-plan-list">{data.pursuits.map(row=><article key={row.id} className="capture-plan-card"><header><div><span>{human(row.stage)} · {row.agency}</span><h3>{row.title}</h3><p>{row.owner_name||"Owner unassigned"} · {row.age_days} days in portfolio · {row.stale_days} days since update</p></div><div><strong>{money.format(Number(row.estimated_value||0))}</strong><small>{row.probability_of_win}% Pwin · {money.format(Number(row.weighted_value||0))} weighted</small></div></header>
    <div className="capture-plan-actions"><label><span>Governed transition</span><select defaultValue="" disabled={busy||!row.allowed_transitions.length} onChange={event=>{const stage=event.target.value;if(stage)void mutate({action:"transition",pursuit_id:row.id,stage},`Moved ${row.title} to ${human(stage)}.`)}}><option value="">Select next stage</option>{row.allowed_transitions.map(stage=><option value={stage} key={stage}>{human(stage)}</option>)}</select></label>{!row.plan?<div className="capture-template-actions">{data.templates.map(template=><button className="secondary-button" key={template.key} disabled={busy} onClick={()=>void mutate({action:"apply_template",pursuit_id:row.id,template_key:template.key},`${template.name} capture plan applied.`)}>{template.name} ({template.milestone_count})</button>)}</div>:<span className="capture-progress">{row.plan.progress_percent}% complete</span>}</div>
    {row.gate_findings.length?<div className="capture-gate-findings"><strong>Current gate evidence</strong>{row.gate_findings.map(item=><span key={item}>• {item}</span>)}</div>:<div className="capture-gate-ready"><CheckCircle2 size={16}/> Current gate evidence is complete.</div>}
    {row.plan&&<><div className="capture-plan-fields"><label><span>Capture objective</span><textarea defaultValue={row.plan.objective} onBlur={event=>void mutate({action:"update_plan",plan_id:row.plan?.id,objective:event.target.value},"Capture objective saved.")}/></label><label><span>Customer need</span><textarea defaultValue={row.plan.customer_need} onBlur={event=>void mutate({action:"update_plan",plan_id:row.plan?.id,customer_need:event.target.value},"Customer need saved.")}/></label><label><span>Win strategy</span><textarea defaultValue={row.plan.win_strategy} onBlur={event=>void mutate({action:"update_plan",plan_id:row.plan?.id,win_strategy:event.target.value},"Win strategy saved.")}/></label></div><div className="capture-milestones">{row.plan.milestones.map(milestone=><button key={milestone.id} disabled={busy||milestone.blocked} className={milestone.completed_at?"complete":""} onClick={()=>void mutate({action:"complete_milestone",milestone_id:milestone.id,complete:!milestone.completed_at},milestone.completed_at?"Milestone reopened.":"Milestone completed.")}>{milestone.completed_at?<CheckCircle2/>:<Circle/>}<span><strong>{milestone.title}</strong><small>{human(milestone.category)}{milestone.blocked?" · Waiting on prerequisite":""}</small></span></button>)}</div></>}
   </article>)}</div>
  </section>

  <section className="capture-ops-grid">
   <article className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">WEEK OF {data.weekly_review.week_start}</span><h2>Weekly capture review</h2></div><span className={`status-pill ${data.weekly_review.status}`}>{human(data.weekly_review.status)}</span></div><textarea rows={7} value={notes} onChange={event=>setNotes(event.target.value)} placeholder="Decisions, owners, constraints, and next-week commitments…"/><div className="row-actions"><button className="secondary-button" disabled={busy} onClick={()=>void mutate({action:"record_weekly_review",notes,complete:false},"Weekly review draft saved.")}>Save draft</button><button className="primary-button" disabled={busy} onClick={()=>void mutate({action:"record_weekly_review",notes,complete:true},"Weekly capture review completed.")}><ClipboardCheck size={16}/> Complete review</button></div></article>
   <article className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CONCENTRATION</span><h2>Agency exposure</h2></div></div><div className="capture-concentration">{data.agency_concentration.map(row=><div key={row.agency}><span><strong>{row.agency}</strong><small>{money.format(Number(row.value||0))}</small></span><i><b style={{width:`${Math.min(100,row.share_percent)}%`}}/></i><em>{row.share_percent}%</em></div>)}</div></article>
  </section>

  <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">AUDIT HISTORY</span><h2>Stage and probability changes</h2></div></div><div className="capture-change-list">{data.recent_changes.map(row=><div key={row.id}><time>{new Date(row.created_at).toLocaleString()}</time><strong>{row.title}</strong><span>{human(row.previous_stage)} → {human(row.new_stage)}</span><span>{row.previous_probability}% → {row.new_probability}%</span><small>{row.changed_by}{row.reason?` · ${row.reason}`:""}</small></div>)}</div></section>
 </main>;
}
