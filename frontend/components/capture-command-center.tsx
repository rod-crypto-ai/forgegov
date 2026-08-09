"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, AlertTriangle, Brain, CalendarClock, CheckCircle2, CircleDollarSign, Clock3, FileWarning, Gauge, Handshake, History, LoaderCircle, NotebookPen, RefreshCw, ShieldCheck, Target, UsersRound } from "lucide-react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type CommandCenterPayload = {
  generated_at:string;
  opportunity:{source_id:string;title:string;agency?:string;solicitation_number?:string};
  scores:Record<string,number>;
  bid_decision:{recommendation?:string;confidence?:number;rationale?:string[]};
  summary:string;
  health:{readiness_gaps:number;compliance_missing:number;open_tasks:number;competitor_signals:number;teaming_matches:number};
  next_actions:Array<{priority:string;title:string;reason:string;href?:string}>;
  risks:Array<{key:string;label:string;score:number;severity:string;reason:string;mitigation:string}>;
  readiness:Array<{key:string;label:string;status:string;detail:string}>;
  competition:{incumbent:Record<string,unknown>;competitors:Array<Record<string,unknown>>;similar_contracts:Array<Record<string,unknown>>};
  teaming:Array<Record<string,unknown>>;
  compliance:Array<{key:string;requirement:string;category:string;source:string;status:string;owner:string;evidence:string}>;
  pricing_readiness:{score?:number;status?:string;warning?:string};
  win_strategy:{strengths?:string[];gaps?:string[];discriminators?:string[];customer_evaluation_hypotheses?:string[];warning?:string};
  timeline:Array<{label:string;date:string;source:string;kind:string;category?:string}>;
  proposal_tasks:Array<{id:string;title:string;status:string;priority:string;due_at?:string|null;source:string;assigned_to:string}>;
  capture_memory:Array<{type:string;title:string;content:string;updated_at?:string|null;visibility?:string;model?:string}>;
  project_room?:{id:number;name:string;href:string}|null;
  pursuit_decision?:{decision:{recommendation:string;score:number;win_probability:number;confidence:number;evidence_coverage:number;conditions:string[];hard_blockers:string[]};economics:{estimated_value?:string|number|null;expected_value?:string|number|null};warning:string};
  warnings:string[];
};

const text=(value:unknown,fallback="—")=>value===null||value===undefined||value===""?fallback:String(value);
const scoreTone=(value:number)=>value>=75?"strong":value>=50?"watch":"risk";

export function CaptureCommandCenter({noticeId}:{noticeId:string}){
  const [data,setData]=useState<CommandCenterPayload|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const endpoint=`/ai/opportunities/${encodeURIComponent(noticeId)}/command-center/`;
  const load=useCallback(async()=>{setBusy(true);try{setData(await apiGet<CommandCenterPayload>(endpoint));setMessage("")}catch(error){setMessage(error instanceof Error?error.message:"Command Center could not be loaded")}finally{setBusy(false)}},[endpoint]);
  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
  if(!data)return <section className="data-panel capture-command-loading">{message?<><AlertTriangle/><strong>Capture Command Center unavailable</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></>:<><LoaderCircle className="spin"/><strong>Building Capture Command Center</strong><p>Combining capture health, win strategy, proposal tasks, collaboration memory, and market evidence.</p></>}</section>;

  const health=Number(data.scores.health??0);const win=Number(data.scores.win_probability??0);const ready=Number(data.scores.proposal_readiness??0);
  const decision=text(data.bid_decision.recommendation,"hold").replaceAll("_"," ");
  const incumbent=text(data.competition.incumbent.recipient_name||data.competition.incumbent.name,"No reliable signal");
  return <section className="capture-command-shell">
    <header className="capture-command-header"><div><span className="eyebrow">CAPTURE COMMAND CENTER</span><h2>Run the pursuit from one screen</h2><p>Capture decision support, win strategy, proposal work, collaboration memory, and official market evidence in one operational view.</p></div><button className="secondary-button" disabled={busy} onClick={()=>void load()}>{busy?<LoaderCircle className="spin" size={16}/>:<RefreshCw size={16}/>} Refresh command center</button></header>
    {message&&<p className="inline-message">{message}</p>}

    <div className="capture-command-kpis">
      <article className={`command-kpi ${scoreTone(health)}`}><span><Gauge size={17}/>Opportunity health</span><strong>{health}<small>/100</small></strong><p>{data.health.readiness_gaps} readiness gap(s)</p></article>
      <article className={`command-kpi ${scoreTone(win)}`}><span><Target size={17}/>Win probability</span><strong>{win}<small>%</small></strong><p>Decision-support estimate</p></article>
      <article className={`command-kpi ${scoreTone(ready)}`}><span><ShieldCheck size={17}/>Proposal readiness</span><strong>{ready}<small>/100</small></strong><p>{data.health.compliance_missing} missing compliance row(s)</p></article>
      <article className={`command-kpi decision ${decision==="bid"?"strong":decision==="no bid"?"risk":"watch"}`}><span><CheckCircle2 size={17}/>Bid posture</span><strong>{decision.toUpperCase()}</strong><p>{Number(data.bid_decision.confidence??0)}% evidence confidence</p></article>
    </div>

    {data.pursuit_decision&&<section className="data-panel pursuit-decision-banner"><div><span className="eyebrow">PURSUIT DECISION INTELLIGENCE</span><h3>{data.pursuit_decision.decision.recommendation}</h3><p>{data.pursuit_decision.decision.conditions[0]||"Current evidence supports the recommendation without a material condition."}</p></div><div className="pursuit-decision-metrics"><span><b>{data.pursuit_decision.decision.win_probability}%</b> win probability</span><span><b>{data.pursuit_decision.decision.confidence}%</b> confidence</span><span><b>{data.pursuit_decision.decision.evidence_coverage}%</b> evidence</span><span><b>{data.pursuit_decision.economics.expected_value?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(data.pursuit_decision.economics.expected_value)):"—"}</b> expected value</span></div><small>{data.pursuit_decision.warning}</small></section>}

    <div className="capture-command-primary">
      <section className="data-panel command-executive"><div className="panel-title-row"><div><span className="eyebrow">EXECUTIVE BRIEF</span><h3>Current pursuit posture</h3></div><Brain size={20}/></div><p className="command-summary">{data.summary}</p><div className="command-rationale">{(data.bid_decision.rationale??[]).slice(0,5).map((row,index)=><p key={index}><span/><>{row}</></p>)}</div><div className="command-shortcuts"><Link href="#" onClick={e=>e.preventDefault()}>Health {health}</Link><span>Incumbent: {incumbent}</span><span>{data.health.competitor_signals} competitor signal(s)</span><span>{data.health.teaming_matches} partner match(es)</span></div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PRIORITY QUEUE</span><h3>What the team should do next</h3></div><Activity size={20}/></div><div className="command-action-list">{data.next_actions.length?data.next_actions.map((row,index)=><article className={row.priority} key={`${row.title}-${index}`}><span>{row.priority}</span><div><strong>{row.title}</strong><p>{row.reason}</p>{row.href?<Link href={row.href}>Open workflow →</Link>:null}</div></article>):<p className="strategy-muted">No priority actions are currently queued.</p>}</div></section>
    </div>

    <div className="capture-command-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PROPOSAL PLAN</span><h3>Open work</h3></div><CalendarClock size={20}/></div><div className="command-task-list">{data.proposal_tasks.length?data.proposal_tasks.slice(0,12).map(row=><article key={row.id}><span className={`task-state ${row.status}`}/><div><strong>{row.title}</strong><p>{row.assigned_to} · {row.source}</p></div><small>{row.due_at?new Date(row.due_at).toLocaleDateString():"No due date"}</small></article>):<div className="table-state compact-state"><CalendarClock/><strong>No proposal tasks yet</strong><p>Create workspace or Project Room tasks to build the execution plan.</p></div>}</div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CAPTURE MEMORY</span><h3>What the organization knows</h3></div><NotebookPen size={20}/></div><div className="command-memory-list">{data.capture_memory.length?data.capture_memory.slice(0,10).map((row,index)=><article key={`${row.title}-${index}`}><div><span>{row.type.replaceAll("_"," ")}</span><small>{row.updated_at?new Date(row.updated_at).toLocaleString():""}</small></div><strong>{row.title}</strong><p>{row.content.slice(0,320)}{row.content.length>320?"…":""}</p></article>):<div className="table-state compact-state"><NotebookPen/><strong>No capture memory yet</strong><p>Pipeline notes, Project Room notes, and saved ForgeAI analyses will appear here.</p></div>}</div>{data.project_room?<Link className="secondary-button command-room-link" href={data.project_room.href}>Open {data.project_room.name}</Link>:null}</section>
    </div>

    <div className="capture-command-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">RISK WATCH</span><h3>Capture risks</h3></div><FileWarning size={20}/></div><div className="command-risk-grid">{data.risks.map(row=><article className={row.severity} key={row.key}><div><strong>{row.label}</strong><span>{row.severity}</span></div><p>{row.reason}</p><small>{row.mitigation}</small></article>)}</div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">MARKET + TEAMING</span><h3>Competitive position</h3></div><UsersRound size={20}/></div><div className="command-market-grid"><article><span>Likely incumbent signal</span><strong>{incumbent}</strong><small>{text(data.competition.incumbent.classification,"Evidence unavailable").replaceAll("_"," ")}</small></article><article><span>Likely competitors</span><strong>{data.competition.competitors.length}</strong><small>Historical-award inference</small></article><article><span>Teaming matches</span><strong>{data.teaming.length}</strong><small>ForgeGov Network</small></article><article><span>Pricing readiness</span><strong>{Number(data.pricing_readiness.score??0)}%</strong><small>{text(data.pricing_readiness.status,"unknown").replaceAll("_"," ")}</small></article></div></section>
    </div>

    <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">INTELLIGENCE TIMELINE</span><h3>Acquisition + capture activity</h3></div><History size={20}/></div><div className="command-timeline">{data.timeline.slice(0,16).map((row,index)=><article key={`${row.label}-${index}`}><span className={`timeline-marker ${row.category??"capture"}`}/><div><strong>{row.label}</strong><p>{row.source}</p></div><time>{row.date?new Date(row.date).toLocaleString():"Date unavailable"}</time></article>)}</div></section>

    <section className="command-warning"><AlertTriangle size={17}/><div>{data.warnings.map((row,index)=><p key={index}>{row}</p>)}</div></section>
  </section>;
}
