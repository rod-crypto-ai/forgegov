"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import { ArrowUp, Bot, ExternalLink, FileSearch, Globe2, LoaderCircle, ShieldCheck, Sparkles, Target, Users } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

const prompts = [
  { icon: FileSearch, title: "Opportunity brief", text: "Summarize scope, deadlines, requirements, risks, and unanswered questions." },
  { icon: Target, title: "Bid/no-bid analysis", text: "Evaluate fit, timing, competition, compliance, and recommended action." },
  { icon: Users, title: "Teaming strategy", text: "Identify capability gaps and the strongest partner profile for this pursuit." },
  { icon: Globe2, title: "Live market research", text: "Combine ForgeGov records with current web research when live search is configured." },
];

type Source = { label:string; type:string; title:string; url?:string };
type Message = { role:"user"|"assistant"; content:string; model?:string; provider?:string; sources?:Source[] };
type IntegrationStatus = { openai?:{configured?:boolean;model?:string}; ai?:{provider?:string;model?:string;web_search?:boolean} };
type AiResponse = { answer:string; model:string; provider?:string; sources?:Source[]; web_enabled?:boolean };

function StructuredAnswer({content}:{content:string}) {
  const blocks=useMemo(()=>content.split(/\n{2,}/).map(v=>v.trim()).filter(Boolean),[content]);
  return <div className="structured-ai-answer">{blocks.map((block,index)=>{
    const lines=block.split("\n").map(v=>v.trim()).filter(Boolean);
    const first=lines[0]?.replace(/^#{1,6}\s*/,"").replace(/^\*\*(.+)\*\*:?$/,"$1");
    const heading=/^#{1,6}\s/.test(lines[0]??"") || /^\*\*.+\*\*:?$/.test(lines[0]??"") || (/^[A-Z][A-Za-z /&-]{2,40}:?$/.test(first??"") && lines.length>1);
    const body=heading?lines.slice(1):lines;
    return <section className="ai-insight-card" key={index}>{heading&&<h3>{first?.replace(/:$/,"")}</h3>}<div>{body.map((line,i)=>/^[-•*]\s+/.test(line)?<div className="ai-bullet" key={i}><span/> <p>{line.replace(/^[-•*]\s+/,"")}</p></div>:<p key={i}>{line}</p>)}</div></section>;
  })}</div>;
}

export function AssistantWorkspace(){
 const[prompt,setPrompt]=useState("");const[messages,setMessages]=useState<Message[]>([]);const[loading,setLoading]=useState(false);const[error,setError]=useState("");const[configured,setConfigured]=useState<boolean|null>(null);const[model,setModel]=useState("");const[provider,setProvider]=useState("openai");const[webEnabled,setWebEnabled]=useState(false);
 useEffect(()=>{let active=true;apiGet<IntegrationStatus>("/integrations/status/").then(status=>{if(!active)return;setConfigured(Boolean(status.openai?.configured)||status.ai?.provider==="ollama");setModel(status.ai?.model??status.openai?.model??"");setProvider(status.ai?.provider??"openai");setWebEnabled(Boolean(status.ai?.web_search));}).catch(()=>active&&setConfigured(null));return()=>{active=false}},[]);
 async function submit(event:FormEvent){event.preventDefault();const text=prompt.trim();if(!text||loading)return;const history=messages.map(({role,content})=>({role,content}));setMessages(c=>[...c,{role:"user",content:text}]);setPrompt("");setError("");setLoading(true);try{const response=await apiPost<AiResponse>("/ai/chat/",{message:text,history});setMessages(c=>[...c,{role:"assistant",content:response.answer,model:response.model,provider:response.provider,sources:response.sources}]);setConfigured(true);setModel(response.model);setProvider(response.provider??provider);setWebEnabled(Boolean(response.web_enabled));}catch(e){const message=e instanceof Error?e.message:"ForgeGov AI could not complete the request.";setError(message);}finally{setLoading(false)}}
 return <div className="assistant-layout modern-ai-layout"><section className="assistant-main"><header className="assistant-heading"><span className="assistant-mark"><Sparkles size={24}/></span><div><span className="eyebrow">RESEARCH + CAPTURE COPILOT</span><h1>ForgeGov AI</h1><p>Ask any GovCon question using workspace intelligence and optional live web research.</p></div><div className="ai-mode-badges"><span>{provider==="ollama"?"Open-source model":"Hosted model"}</span><span className={webEnabled?"live":"pending"}>{webEnabled?"Live web on":"Web search optional"}</span></div></header>
 {!messages.length?<div className="assistant-empty"><div className="ai-orb"><Bot size={36}/></div><h2>What do you need to know?</h2><p>Use a guided workflow or ask a free-form question about opportunities, awards, agencies, competitors, clauses, pricing, capture strategy, or current market activity.</p><div className="prompt-grid">{prompts.map(item=>{const Icon=item.icon;return <button key={item.title} onClick={()=>setPrompt(item.title)}><Icon size={20}/><strong>{item.title}</strong><span>{item.text}</span></button>})}</div></div>:<div className="chat-thread">{messages.map((message,index)=><article key={index} className={`chat-message ${message.role}`}><header><strong>{message.role==="user"?"You":"ForgeGov AI"}</strong>{message.model&&<small>{message.provider??provider} · {message.model}</small>}</header>{message.role==="assistant"?<StructuredAnswer content={message.content}/>:<p>{message.content}</p>}{message.sources?.length?<div className="ai-source-list"><span>Sources used</span>{message.sources.slice(0,10).map(source=>source.url?<a key={source.label} href={source.url} target="_blank" rel="noreferrer"><b>{source.label}</b>{source.title}<ExternalLink size={12}/></a>:<div key={source.label}><b>{source.label}</b>{source.title}</div>)}</div>:null}</article>)}{loading&&<div className="chat-message assistant"><strong>ForgeGov AI</strong><p className="ai-thinking"><LoaderCircle className="spin" size={17}/> Researching records and available live sources…</p></div>}</div>}
 {error&&<p className="assistant-error">{error}</p>}<form className="assistant-composer" onSubmit={submit}><textarea value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder="Ask about an opportunity, agency, competitor, FAR clause, market, or capture action…" disabled={loading} maxLength={8000}/><div><span><ShieldCheck size={15}/> Facts are grounded and sources are shown</span><button type="submit" aria-label="Send" disabled={loading||!prompt.trim()}>{loading?<LoaderCircle className="spin" size={18}/>:<ArrowUp size={18}/>}</button></div></form></section>
 <aside className="assistant-context"><span className="eyebrow">AI CONFIGURATION</span><h2>Research sources</h2><div className="context-source"><span className={`status-dot ${configured?"live":"pending"}`}/><div><strong>{provider==="ollama"?"Self-hosted Ollama":"OpenAI API"}</strong><small>{configured?`${model||"Configured model"} ready`:"Provider needs configuration"}</small></div></div><div className="context-source"><span className={`status-dot ${webEnabled?"live":"pending"}`}/><div><strong>Live web research</strong><small>{webEnabled?"SearXNG search connected":"Add SEARXNG_URL to enable"}</small></div></div><div className="context-source"><span className="status-dot live"/><div><strong>ForgeGov workspace</strong><small>Pipeline, pursuits, tasks, contacts, files</small></div></div><div className="context-source"><span className="status-dot live"/><div><strong>Government records</strong><small>SAM.gov, USAspending, grants, forecasts</small></div></div><div className="context-warning"><ShieldCheck size={18}/><p>Answers separate verified facts, analysis, risks, and recommendations. Missing evidence is identified instead of invented.</p></div></aside></div>;
}
