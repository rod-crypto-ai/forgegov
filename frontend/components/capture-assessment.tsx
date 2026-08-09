"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDot,
  Gauge,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Target,
  TimerReset,
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type ScoreKey = "health" | "win_probability" | "proposal_readiness" | "capability" | "documents" | "compliance" | "schedule" | "pricing" | "competition" | "past_performance";
type CaptureAssessmentPayload = {
  generated_at: string;
  opportunity: { source_id:string; title:string; agency:string; solicitation_number:string; naics:string; psc:string; response_deadline?:string|null };
  scores: Record<ScoreKey, number>;
  bid_decision: { recommendation:"bid"|"hold"|"no_bid"; confidence:number; evidence_coverage:number; rationale:string[]; warning:string };
  executive_summary: string;
  ai_generated: boolean;
  readiness: Array<{ key:string; label:string; status:"complete"|"needs_review"|"missing"; detail:string }>;
  risks: Array<{ key:string; label:string; score:number; severity:"low"|"medium"|"high"; reason:string; mitigation:string }>;
  actions: Array<{ priority:"critical"|"high"|"medium"|"low"; title:string; reason:string; href?:string }>;
  timeline: Array<{ label:string; date:string; source:string; kind:string }>;
  competition: { historical_vendor_count:number; top_historical_vendors:Array<{name:string;matching_awards:number}>; warning:string };
  document_signals: { section_l:boolean; section_m:boolean; clins:number; clauses:number; key_dates:number; certifications:number; deliverables:number };
  pipeline: { id:number|null; stage:string; estimated_value?:number|null; probability_of_win:number; next_action:string; project_room_id:number|null };
};
type DecisionPayload={decision:{recommendation:string;score:number;win_probability:number;confidence:number;evidence_coverage:number;conditions:string[];hard_blockers:string[]};scorecard:Array<{key:string;score:number;weight:number;contribution:number}>;economics:{estimated_value?:string|number|null;expected_value?:string|number|null;target_margin_percent?:string|number|null;pursuit_cost?:string|number|null;subcontractor_share_percent?:string|number|null};competitive_position:{strengths:string[];gaps:string[]};evidence:Array<{label:string;classification:string;available:boolean;detail:string}>;history:Array<{id:number;created_at:string;recommendation:string;win_probability:number;confidence:number;evidence_coverage:number;expected_value?:string|number|null}>;learning_feedback:Array<{status:string;reason:string;lessons_learned:string[]}>;warning:string};

function scoreClass(score:number){return score>=75?"strong":score>=50?"watch":"risk"}
function decisionLabel(value:string){return value==="bid"?"BID":value==="no_bid"?"NO-BID":"HOLD / VALIDATE"}
function readinessIcon(status:string){return status==="complete"?<CheckCircle2 size={17}/>:status==="needs_review"?<CircleDot size={17}/>:<AlertTriangle size={17}/>}

export function CaptureAssessment({noticeId}:{noticeId:string}){
  const[data,setData]=useState<CaptureAssessmentPayload|null>(null);
  const[busy,setBusy]=useState(false);
  const[message,setMessage]=useState("");
  const[decision,setDecision]=useState<DecisionPayload|null>(null);
  const[recording,setRecording]=useState(false);
  const endpoint=`/ai/opportunities/${encodeURIComponent(noticeId)}/capture-assessment/`;
  const decisionEndpoint=`/ai/opportunities/${encodeURIComponent(noticeId)}/pursuit-decision/`;

  const load=useCallback(async()=>{
    try{
      const result=await apiGet<CaptureAssessmentPayload>(endpoint);
      setData(result);
      setMessage("");
    }catch(error){setMessage(error instanceof Error?error.message:"Capture assessment could not be loaded")}
  },[endpoint]);

  useEffect(()=>{let cancelled=false;Promise.all([apiGet<CaptureAssessmentPayload>(endpoint),apiGet<DecisionPayload>(decisionEndpoint)]).then(([result,decisionResult])=>{if(!cancelled){setData(result);setDecision(decisionResult)}}).catch(error=>{if(!cancelled)setMessage(error instanceof Error?error.message:"Capture assessment could not be loaded")});return()=>{cancelled=true}},[endpoint,decisionEndpoint]);

  async function refreshAi(){
    setBusy(true);setMessage("");
    try{const result=await apiPost<CaptureAssessmentPayload>(endpoint,{refresh:true});setData(result);setMessage(result.ai_generated?"ForgeAI executive brief refreshed.":"Capture assessment refreshed. AI provider was unavailable, so evidence-based scoring remains active.")}
    catch(error){setMessage(error instanceof Error?error.message:"ForgeAI capture brief could not be refreshed")}
    finally{setBusy(false)}
  }

  async function recordDecision(){setRecording(true);setMessage("");try{const result=await apiPost<DecisionPayload>(decisionEndpoint,{});setDecision(result);setMessage("Pursuit decision snapshot recorded.")}catch(error){setMessage(error instanceof Error?error.message:"Decision snapshot could not be recorded")}finally{setRecording(false)}}

  const topScores=useMemo(()=>data?[
    {label:"Opportunity health",value:data.scores.health,icon:Gauge},
    {label:"Win probability",value:data.scores.win_probability,icon:Target},
    {label:"Proposal readiness",value:data.scores.proposal_readiness,icon:CheckCircle2},
  ]:[],[data]);

  if(!data)return <section className="data-panel capture-assessment-loading">{message?<><AlertTriangle/><strong>Capture assessment unavailable</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></>:<><LoaderCircle className="spin"/><strong>Building capture assessment</strong><p>Scoring opportunity evidence, document readiness, schedule, pricing, and market signals.</p></>}</section>;

  return <section className="capture-assessment-shell">
    <header className="capture-assessment-header">
      <div><span className="eyebrow">EXECUTIVE CAPTURE INTELLIGENCE</span><h2>Capture assessment</h2><p>Decision support grounded in ForgeGov records, indexed solicitation evidence, pipeline data, and historical award signals.</p></div>
      <button className="secondary-button" disabled={busy} onClick={()=>void refreshAi()}>{busy?<LoaderCircle className="spin" size={16}/>:<RefreshCw size={16}/>} Refresh ForgeAI brief</button>
    </header>
    {message&&<p className="inline-message">{message}</p>}

    <div className="capture-score-row">
      {topScores.map(({label,value,icon:Icon})=><article className={`capture-score-card ${scoreClass(value)}`} key={label}><div><span>{label}</span><Icon size={19}/></div><strong>{value}<small>/100</small></strong><div className="capture-score-track"><i style={{width:`${value}%`}}/></div></article>)}
      <article className={`capture-decision-card ${data.bid_decision.recommendation}`}><div><span>Bid decision</span><ShieldCheck size={19}/></div><strong>{decisionLabel(data.bid_decision.recommendation)}</strong><p>{data.bid_decision.confidence}% confidence · {data.bid_decision.evidence_coverage}% evidence coverage</p></article>
    </div>

    {decision&&<section className="data-panel pursuit-decision-detail"><div className="panel-title-row"><div><span className="eyebrow">PURSUIT DECISION INTELLIGENCE</span><h3>{decision.decision.recommendation}</h3></div><button className="secondary-button" disabled={recording} onClick={()=>void recordDecision()}>{recording?"Recording…":"Record decision snapshot"}</button></div><div className="pursuit-scorecard">{decision.scorecard.map(row=><article key={row.key}><span>{row.key.replaceAll("_"," ")}</span><strong>{row.score}/100</strong><small>{row.weight}% weight · {row.contribution} points</small></article>)}</div><div className="pursuit-decision-columns"><div><h4>Conditions to pursue</h4>{decision.decision.conditions.length?decision.decision.conditions.map((row,index)=><p key={index}>• {row}</p>):<p>No material conditions currently identified.</p>}</div><div><h4>Bid economics</h4><p>Estimated value: <b>{decision.economics.estimated_value?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(decision.economics.estimated_value)):"Not entered"}</b></p><p>Probability-adjusted value: <b>{decision.economics.expected_value?new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(decision.economics.expected_value)):"Not available"}</b></p><p>Decision confidence: <b>{decision.decision.confidence}%</b> · evidence {decision.decision.evidence_coverage}%</p></div></div><div className="pursuit-evidence-list">{decision.evidence.map(row=><article key={row.label} className={row.available?"available":"missing"}><strong>{row.label}</strong><span>{row.classification.replaceAll("_"," ")}</span><p>{row.detail}</p></article>)}</div><small>{decision.warning}</small>{decision.history.length?<div className="pursuit-history"><h4>Decision history</h4>{decision.history.slice(0,5).map(row=><p key={row.id}><b>{row.recommendation}</b> · {row.win_probability}% Pwin · {new Date(row.created_at).toLocaleString()}</p>)}</div>:null}</section>}

    <div className="capture-executive-grid">
      <article className="data-panel capture-summary-card"><div className="panel-title-row"><div><span className="eyebrow">EXECUTIVE BRIEF</span><h3>{data.ai_generated?"ForgeAI assessment":"Evidence-based assessment"}</h3></div><Sparkles size={20}/></div><p className="capture-summary-copy">{data.executive_summary}</p><div className="capture-rationale-list">{data.bid_decision.rationale.slice(0,4).map((row,index)=><div key={index}><span/><p>{row}</p></div>)}</div><small>{data.bid_decision.warning}</small></article>
      <article className="data-panel capture-actions-card"><div className="panel-title-row"><div><span className="eyebrow">NEXT ACTIONS</span><h3>What to do next</h3></div><Target size={20}/></div><div className="capture-action-list">{data.actions.slice(0,6).map((row,index)=><article className={row.priority} key={`${row.title}-${index}`}><span>{row.priority}</span><div><strong>{row.title}</strong><p>{row.reason}</p></div></article>)}</div></article>
    </div>

    <div className="capture-detail-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PROPOSAL READINESS</span><h3>Evidence checklist</h3></div><strong>{data.scores.proposal_readiness}%</strong></div><div className="capture-readiness-list">{data.readiness.map(row=><article className={row.status} key={row.key}>{readinessIcon(row.status)}<div><strong>{row.label}</strong><p>{row.detail}</p></div><span>{row.status.replaceAll("_"," ")}</span></article>)}</div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CAPTURE RISK</span><h3>Risk posture</h3></div><AlertTriangle size={20}/></div><div className="capture-risk-list">{data.risks.map(row=><article className={row.severity} key={row.key}><div><strong>{row.label}</strong><span>{row.severity}</span></div><div className="capture-risk-meter"><i style={{width:`${row.score}%`}}/></div><p>{row.reason}</p><small>{row.mitigation}</small></article>)}</div></section>
    </div>

    <div className="capture-bottom-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">EVIDENCE COVERAGE</span><h3>Capture inputs</h3></div></div><div className="document-signal-grid"><div><span>Section L</span><strong>{data.document_signals.section_l?"Found":"Missing"}</strong></div><div><span>Section M</span><strong>{data.document_signals.section_m?"Found":"Missing"}</strong></div><div><span>CLIN / ELIN</span><strong>{data.document_signals.clins}</strong></div><div><span>FAR / DFARS</span><strong>{data.document_signals.clauses}</strong></div><div><span>Key dates</span><strong>{data.document_signals.key_dates}</strong></div><div><span>Deliverables</span><strong>{data.document_signals.deliverables}</strong></div></div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CAPTURE TIMELINE</span><h3>Known milestones</h3></div><TimerReset size={20}/></div><div className="capture-timeline-list">{data.timeline.length?data.timeline.slice(0,8).map((row,index)=><article key={`${row.label}-${index}`}><span/><div><strong>{row.label}</strong><p>{row.date}</p><small>{row.source}</small></div></article>):<p>No dated acquisition milestones are available yet.</p>}</div></section>
    </div>
  </section>
}
