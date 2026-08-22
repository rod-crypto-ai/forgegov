"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowUp, Bot, BrainCircuit, Building2, CheckCircle2, ClipboardCheck, ExternalLink, LoaderCircle, RefreshCw, SearchCheck, ShieldCheck, Sparkles, Target, UsersRound } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Source={label:string;title:string;url?:string;type?:string};
type Action={priority:string;title:string;reason:string;href?:string};
type Risk={key?:string;label:string;severity:string;reason:string;mitigation:string};
type Gap={label:string;detail:string;status:string};
type Competitor={name:string;confidence?:number;known_signals?:string[];historical_award_count?:number};
type WinTheme={title:string;status:string;message:string;proof_points?:string[]};
type Brief={
  generated_at:string;
  opportunity:Record<string,unknown>;
  posture:{recommendation?:string;decision_score?:number;win_probability?:number;confidence?:number;evidence_coverage?:number;qualification_score?:number;qualification_recommendation?:string;capture_health?:number;proposal_readiness?:number};
  economics:{restricted?:boolean;detail?:string;estimated_value?:string|number|null;expected_value?:string|number|null;projected_profit?:string|number|null;target_margin_percent?:string|number|null;price_to_win_target?:string|number|null;price_to_win_confidence?:number|null;working_capital_gap?:string|number|null;working_capital_risk?:string};
  priority_actions:Action[];
  top_risks:Risk[];
  evidence_gaps:Gap[];
  conditions:string[];
  hard_blockers:string[];
  competitive:{incumbent:Record<string,unknown>;competitors:Competitor[];agency_buying_history:Record<string,unknown>;win_themes:WinTheme[];teaming:Array<Record<string,unknown>>};
  warnings:string[];
};
type History={id:number;content:string;model:string;updated_at:string;sources?:Source[];contains_financial?:boolean;uses_workspace_context?:boolean};
type LoadPayload={brief:Brief;modes:Array<{key:string;description:string}>;history:History[]};
type RunPayload={mode:string;answer:string;sources:Source[];model:string;analysis_id:number;cached:boolean;brief:Brief};

const modes=[
  ["executive_review","Executive review",BrainCircuit,"Summarize pursuit posture for a leadership review."],
  ["bid_decision","Challenge bid decision",ClipboardCheck,"Stress-test the current go / no-go recommendation."],
  ["customer_strategy","Customer strategy",Building2,"Review agency evidence and build a customer validation plan."],
  ["competitor_review","Competitor review",UsersRound,"Assess historical competitive signals and unknowns."],
  ["proposal_strategy","Proposal strategy",Target,"Turn capture evidence into proposal priorities."],
  ["red_team","Red-team review",AlertTriangle,"Find weak assumptions before they cost proposal resources."],
  ["next_actions","Next actions",CheckCircle2,"Build a prioritized capture action plan."],
] as const;

function fmtMoney(value:unknown){const num=Number(value);if(!Number.isFinite(num)||!num)return "—";return new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",notation:"compact",maximumFractionDigits:1}).format(num)}
function text(value:unknown,fallback="—"){return value===null||value===undefined||value===""?fallback:String(value)}
function StructuredAnswer({content}:{content:string}){const blocks=content.split(/\n{2,}/).map(v=>v.trim()).filter(Boolean);return <div className="copilot-answer-body">{blocks.map((block,index)=>{const lines=block.split("\n").map(v=>v.trim()).filter(Boolean);const first=lines[0]??"";const heading=/^#{1,6}\s/.test(first)||/^\*\*.+\*\*:?$/.test(first)||(/^[A-Za-z][A-Za-z /&-]{2,45}:$/.test(first));const title=first.replace(/^#{1,6}\s*/,"").replace(/^\*\*(.+)\*\*:?$/,"$1").replace(/:$/,"");const body=heading?lines.slice(1):lines;return <section key={index}>{heading&&<h3>{title}</h3>}{body.map((line,i)=>/^[-•*]\s+/.test(line)?<div className="copilot-bullet" key={i}><span/><p>{line.replace(/^[-•*]\s+/,"")}</p></div>:<p key={i}>{line}</p>)}</section>})}</div>}

export function CaptureCopilot({noticeId}:{noticeId:string}){
  const endpoint=`/ai/opportunities/${encodeURIComponent(noticeId)}/capture-copilot/`;
  const [data,setData]=useState<LoadPayload|null>(null);
  const [answer,setAnswer]=useState<RunPayload|null>(null);
  const [question,setQuestion]=useState("");
  const [busy,setBusy]=useState("");
  const [message,setMessage]=useState("");
  const load=useCallback(async()=>{try{setData(await apiGet<LoadPayload>(endpoint));setMessage("")}catch(error){setMessage(error instanceof Error?error.message:"Capture Copilot could not be loaded")}},[endpoint]);
  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
  async function run(mode:string,customQuestion="",refresh=false){setBusy(mode);setMessage("");try{const result=await apiPost<RunPayload>(endpoint,{mode,question:customQuestion,refresh});setAnswer(result);setData(current=>current?{...current,brief:result.brief}:current)}catch(error){setMessage(error instanceof Error?error.message:"Capture Copilot could not complete the review")}finally{setBusy("")}}
  async function ask(event:FormEvent){event.preventDefault();if(!question.trim())return;await run("question",question.trim())}
  const brief=data?.brief;
  const posture=brief?.posture;
  const incumbent=useMemo(()=>text(brief?.competitive?.incumbent?.recipient_name??brief?.competitive?.incumbent?.name,"No reliable incumbent signal"),[brief]);
  if(!brief)return <section className="data-panel table-state"><LoaderCircle className="spin"/><strong>Building Capture Copilot context…</strong><p>{message||"Assembling capture, competitive, proposal-readiness, and decision evidence."}</p></section>;

  return <section className="capture-copilot-shell">
    <header className="copilot-hero"><div><span className="copilot-orb"><Sparkles/></span><div><span className="eyebrow">FORGEAI CAPTURE COPILOT · v3.2.0</span><h2>Decision support for the pursuit team</h2><p>ForgeGov assembles the deterministic evidence first, then lets AI challenge, explain, and turn it into action.</p></div></div><button className="secondary-button" onClick={()=>void load()}><RefreshCw size={15}/>Refresh evidence</button></header>
    {message&&<div className="system-banner warning">{message}</div>}

    <div className="copilot-posture-grid">
      <article><span>Recommendation</span><strong>{text(posture?.recommendation).replaceAll("_"," ")}</strong><small>Decision score {posture?.decision_score??"—"}/100</small></article>
      <article><span>Win probability</span><strong>{posture?.win_probability??"—"}%</strong><small>{posture?.confidence??"—"}% model confidence</small></article>
      <article><span>Evidence coverage</span><strong>{posture?.evidence_coverage??"—"}%</strong><small>{brief.evidence_gaps.length} tracked gap(s)</small></article>
      <article><span>Qualification</span><strong>{posture?.qualification_score??"—"}/100</strong><small>{text(posture?.qualification_recommendation).replaceAll("_"," ")}</small></article>
      <article><span>Expected value</span><strong>{brief.economics.restricted?"Restricted":fmtMoney(brief.economics.expected_value)}</strong><small>{brief.economics.restricted?"Authorized financial roles only":"Modeled—not guaranteed"}</small></article>
      <article><span>Likely incumbent</span><strong>{incumbent}</strong><small>Historical evidence signal</small></article>
    </div>

    <div className="copilot-mode-grid">{modes.map(([mode,label,Icon,description])=><button key={mode} disabled={busy!==""} onClick={()=>void run(mode)}><span><Icon/></span><div><strong>{label}</strong><small>{description}</small></div>{busy===mode?<LoaderCircle className="spin"/>:<ArrowUp/>}</button>)}</div>

    {data?.history?.length?<section className="data-panel copilot-history"><div className="panel-title-row"><div><span className="eyebrow">RECENT REVIEWS</span><h3>Your saved Capture Copilot analyses</h3></div><BrainCircuit/></div><div>{data.history.slice(0,4).map(row=><article key={row.id}><div><strong>{row.model||"Configured AI model"}</strong><span>{new Date(row.updated_at).toLocaleString()}</span></div><p>{row.content.slice(0,220)}{row.content.length>220?"…":""}</p><small>{row.contains_financial?"Financial context":"Non-financial context"} · {row.uses_workspace_context?"Workspace grounded":"Private workspace excluded"}</small></article>)}</div></section>:null}

    <div className="copilot-evidence-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PRIORITY ACTIONS</span><h3>What should move now</h3></div><CheckCircle2/></div><div className="copilot-action-list">{brief.priority_actions.slice(0,8).map((row,index)=><article key={`${row.title}-${index}`} className={row.priority}><span>{row.priority}</span><div><strong>{row.title}</strong><p>{row.reason}</p></div></article>)}</div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">EVIDENCE GAPS</span><h3>What still needs proof</h3></div><SearchCheck/></div><div className="copilot-gap-list">{brief.evidence_gaps.length?brief.evidence_gaps.slice(0,8).map((row,index)=><article key={`${row.label}-${index}`}><ShieldCheck/><div><strong>{row.label}</strong><p>{row.detail||"Additional validation required."}</p><small>{row.status.replaceAll("_"," ")}</small></div></article>):<div className="table-state compact-state"><CheckCircle2/><strong>No major evidence gaps detected</strong><p>Continue validating the official solicitation and customer intelligence.</p></div>}</div></section>
    </div>

    <div className="copilot-evidence-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">RISK CHALLENGE</span><h3>Top capture risks</h3></div><AlertTriangle/></div><div className="copilot-risk-list">{brief.top_risks.slice(0,6).map((row,index)=><article key={`${row.label}-${index}`} className={row.severity}><div><strong>{row.label}</strong><span>{row.severity}</span></div><p>{row.reason}</p><small>{row.mitigation}</small></article>)}</div></section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">COMPETITION</span><h3>Historical competitor signals</h3></div><UsersRound/></div><div className="copilot-competitor-list">{brief.competitive.competitors.length?brief.competitive.competitors.slice(0,6).map((row,index)=><article key={`${row.name}-${index}`}><div><strong>{row.name}</strong><span>{row.confidence??"—"}% confidence</span></div><p>{row.known_signals?.slice(0,2).join(" · ")||`${row.historical_award_count??0} stored historical award(s)`}</p></article>):<div className="table-state compact-state"><UsersRound/><strong>No reliable competitor dossier yet</strong><p>More award history or predecessor research is needed.</p></div>}</div></section>
    </div>

    <section className="data-panel copilot-conversation"><div className="panel-title-row"><div><span className="eyebrow">ASK THE COPILOT</span><h3>Challenge the capture plan</h3></div><Bot/></div>{answer?<article className="copilot-answer"><header><div><span>{answer.mode.replaceAll("_"," ")}</span><strong>ForgeGov AI</strong></div><small>{answer.cached?"Reused current evidence analysis":`Generated with ${answer.model||"configured model"}`}</small></header><StructuredAnswer content={answer.answer}/>{answer.sources?.length?<details><summary>Evidence sources ({answer.sources.length})</summary>{answer.sources.slice(0,12).map((source,index)=>source.url?<a key={`${source.label}-${index}`} href={source.url} target="_blank" rel="noreferrer"><b>{source.label}</b>{source.title}<ExternalLink size={12}/></a>:<div key={`${source.label}-${index}`}><b>{source.label}</b>{source.title}</div>)}</details>:null}</article>:<div className="copilot-empty"><BrainCircuit/><strong>Pick a review above or ask a pursuit-specific question.</strong><p>The deterministic posture remains visible even when the AI provider is unavailable.</p></div>}
      <form className="copilot-composer" onSubmit={ask}><textarea value={question} onChange={e=>setQuestion(e.target.value)} placeholder="Example: What are the three assumptions most likely to make us regret bidding this opportunity?" maxLength={12000}/><div><span><ShieldCheck size={14}/>Grounded in authorized ForgeGov evidence</span><button disabled={busy!==""||!question.trim()}>{busy==="question"?<LoaderCircle className="spin"/>:<ArrowUp/>}</button></div></form>
    </section>
  </section>
}
