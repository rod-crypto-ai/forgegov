"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, BadgeCheck, Building2, CheckCircle2, ExternalLink, LoaderCircle, RefreshCw, ShieldCheck, Target, UsersRound } from "lucide-react";
import Link from "next/link";
import { apiGet } from "@/lib/api";

type WinStrategyPayload = {
  generated_at: string;
  opportunity: { source_id:string; title:string; agency:string; naics:string; psc:string; source_url:string };
  incumbent: Record<string, unknown>;
  competitors: Array<Record<string, unknown>>;
  similar_contracts: Array<Record<string, unknown>>;
  teaming_recommendations: Array<Record<string, unknown>>;
  compliance_matrix: Array<{key:string;requirement:string;category:string;source:string;status:string;owner:string;evidence:string}>;
  pricing_readiness: {score:number;status:string;checks:Array<{key:string;complete:boolean;detail:string}>;warning:string};
  win_strategy: {strengths:string[];gaps:string[];discriminators:string[];customer_evaluation_hypotheses:string[];warning:string};
  recommended_actions: Array<{priority:string;title:string;reason:string;href?:string}>;
  labels: Record<string,string>;
};

const money = new Intl.NumberFormat("en-US", { style:"currency", currency:"USD", maximumFractionDigits:0 });
const text = (value: unknown, fallback = "—") => value === null || value === undefined || value === "" ? fallback : String(value);

export function WinStrategy({ noticeId }:{ noticeId:string }){
  const [data,setData]=useState<WinStrategyPayload|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState(false);
  const endpoint=`/ai/opportunities/${encodeURIComponent(noticeId)}/win-strategy/`;

  const load=useCallback(async()=>{
    setBusy(true);
    try{
      const result=await apiGet<WinStrategyPayload>(endpoint);
      setData(result);
      setMessage("");
    }catch(error){setMessage(error instanceof Error?error.message:"Win strategy could not be loaded")}
    finally{setBusy(false)}
  },[endpoint]);

  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);

  if(!data)return <section className="data-panel win-strategy-loading">{message?<><AlertTriangle/><strong>Win strategy unavailable</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></>:<><LoaderCircle className="spin"/><strong>Building win strategy</strong><p>Comparing official award history, solicitation evidence, pricing readiness, and ForgeGov teaming profiles.</p></>}</section>;

  const incumbentName=text(data.incumbent.recipient_name || data.incumbent.name, "No reliable incumbent signal");
  const incumbentStatus=text(data.incumbent.status,"not_found");
  const incumbentConfidence=Number(data.incumbent.confidence??0);

  return <section className="win-strategy-shell">
    <header className="win-strategy-header"><div><span className="eyebrow">COMPETITION + WIN STRATEGY</span><h2>Win strategy workspace</h2><p>Official award evidence is separated from ForgeGov inference. Likely competitors are not presented as official bidders.</p></div><button className="secondary-button" disabled={busy} onClick={()=>void load()}>{busy?<LoaderCircle className="spin" size={16}/>:<RefreshCw size={16}/>} Refresh evidence</button></header>
    {message&&<p className="inline-message">{message}</p>}

    <div className="win-strategy-kpis">
      <article className="win-kpi-card"><span>Incumbent signal</span><strong>{incumbentName}</strong><p>{incumbentStatus==="likely"?`${incumbentConfidence}% evidence confidence`:text(data.incumbent.reason,"More award history is required")}</p><small>Derived from official historical awards</small></article>
      <article className="win-kpi-card"><span>Likely competitors</span><strong>{data.competitors.length}</strong><p>Historical overlap candidates</p><small>Inference — not an official bidder list</small></article>
      <article className="win-kpi-card"><span>Similar contracts</span><strong>{data.similar_contracts.length}</strong><p>Comparable official awards</p><small>USAspending / stored federal awards</small></article>
      <article className="win-kpi-card"><span>Pricing readiness</span><strong>{data.pricing_readiness.score}<small>/100</small></strong><p>{data.pricing_readiness.status.replaceAll("_"," ")}</p><small>Evidence coverage, not a bid-price estimate</small></article>
    </div>

    <div className="win-strategy-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">WIN STRATEGY</span><h3>Evidence-backed posture</h3></div><Target size={20}/></div><div className="strategy-column-grid"><div><strong>Strengths</strong>{data.win_strategy.strengths.map((row,index)=><p className="strategy-line positive" key={`s-${index}`}><CheckCircle2 size={15}/>{row}</p>)}</div><div><strong>Gaps</strong>{data.win_strategy.gaps.map((row,index)=><p className="strategy-line negative" key={`g-${index}`}><AlertTriangle size={15}/>{row}</p>)}</div><div><strong>Potential discriminators</strong>{data.win_strategy.discriminators.length?data.win_strategy.discriminators.map((row,index)=><p className="strategy-line" key={`d-${index}`}><BadgeCheck size={15}/>{row}</p>):<p className="strategy-muted">No discriminator is yet supported strongly enough by stored evidence.</p>}</div><div><strong>Evaluation / customer hypotheses</strong>{data.win_strategy.customer_evaluation_hypotheses.map((row,index)=><p className="strategy-line" key={`h-${index}`}><ShieldCheck size={15}/>{row}</p>)}</div></div><small className="panel-warning-copy">{data.win_strategy.warning}</small></section>

      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PRIORITY ACTIONS</span><h3>What to do next</h3></div></div><div className="win-action-list">{data.recommended_actions.map((row,index)=><article className={row.priority} key={`${row.title}-${index}`}><span>{row.priority}</span><div><strong>{row.title}</strong><p>{row.reason}</p>{row.href?<Link href={row.href}>Open workflow →</Link>:null}</div></article>)}</div></section>
    </div>

    <div className="win-detail-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">COMPETITION</span><h3>Likely competitors</h3></div><Building2 size={20}/></div><div className="competition-card-list">{data.competitors.length?data.competitors.map((row,index)=><article key={`${text(row.name)}-${index}`}><div><strong>{text(row.name)}</strong><span>{Number(row.confidence??0)}% confidence</span></div><p>{text(row.reason)}</p><small>{Number(row.historical_awards??0)} similar awards · {money.format(Number(row.historical_obligated??0))} obligated</small></article>):<div className="table-state compact-state"><Target/><strong>No competitor evidence yet</strong><p>Synchronize more award history or broaden the opportunity classification evidence.</p></div>}</div></section>

      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">TEAMING</span><h3>Recommended partners</h3></div><UsersRound size={20}/></div><div className="competition-card-list">{data.teaming_recommendations.length?data.teaming_recommendations.map((row,index)=><article key={`${text(row.name)}-${index}`}><div><Link className="entity-link" href={text(row.href,"/network")}><strong>{text(row.name)}</strong></Link><span>{Number(row.score??0)}% fit</span></div><p>{Array.isArray(row.reasons)?row.reasons.map(String).join(" · "):"ForgeGov Network match"}</p><small>{text(row.state,"Location not provided")} · relationship {text(row.connection_status,"none")}</small></article>):<div className="table-state compact-state"><UsersRound/><strong>No partner match yet</strong><p>Complete company profiles and required capability evidence to improve matches.</p></div>}</div></section>
    </div>

    <section className="data-panel compliance-matrix-panel"><div className="panel-title-row"><div><span className="eyebrow">COMPLIANCE MATRIX</span><h3>Extracted requirement evidence</h3></div><small>{data.compliance_matrix.length} rows</small></div><div className="responsive-compliance-table"><div className="compliance-table-head"><span>Requirement</span><span>Category</span><span>Source</span><span>Status</span><span>Owner</span></div>{data.compliance_matrix.slice(0,50).map(row=><article key={row.key}><div><strong>{row.requirement}</strong><small>{row.evidence}</small></div><span>{row.category.replaceAll("_"," ")}</span><span>{row.source}</span><span className={`matrix-status ${row.status}`}>{row.status.replaceAll("_"," ")}</span><span>{row.owner}</span></article>)}</div></section>

    <div className="win-detail-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PRICING READINESS</span><h3>Can we build a defensible price?</h3></div><strong>{data.pricing_readiness.score}%</strong></div><div className="pricing-check-list">{data.pricing_readiness.checks.map(row=><article key={row.key}>{row.complete?<CheckCircle2 size={16}/>:<AlertTriangle size={16}/>}<p>{row.detail}</p></article>)}</div><small>{data.pricing_readiness.warning}</small></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">SIMILAR CONTRACTS</span><h3>Historical benchmarks</h3></div></div><div className="similar-contract-list">{data.similar_contracts.slice(0,8).map((row,index)=><article key={`${text(row.award_id)}-${index}`}><div><strong>{text(row.recipient_name)}</strong><span>{Number(row.match_score??0)}% match</span></div><p>{text(row.award_number,"Award number unavailable")} · {text(row.agency,"Agency unavailable")}</p><small>{money.format(Number(row.obligated_amount??0))} obligated · {Array.isArray(row.match_reasons)?row.match_reasons.map(String).join(" · "):"Historical match"}</small>{row.source_url?<a href={text(row.source_url)} target="_blank" rel="noreferrer">Official award <ExternalLink size={12}/></a>:null}</article>)}</div></section>
    </div>
  </section>;
}
