"use client";

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { ArrowUp, Bot, Check, Clipboard, ExternalLink, FileSearch, Globe2, History, LoaderCircle, Plus, ShieldCheck, Sparkles, Target, Users } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

const prompts = [
  { icon: FileSearch, title: "Opportunity brief", text: "Summarize the most relevant opportunity records, deadlines, requirements, risks, and unanswered questions. Use live web research for current facts when available." },
  { icon: Target, title: "Bid/no-bid analysis", text: "Evaluate fit, timing, competition, compliance, likely delivery risk, and the recommended bid/no-bid action." },
  { icon: Users, title: "Teaming strategy", text: "Identify likely capability gaps, recommended partner qualifications, and a practical teaming outreach plan." },
  { icon: Globe2, title: "Live market research", text: "Research the current government-contracting market using ForgeGov records and live web sources. Separate verified facts from analysis." },
];

type Source = { label: string; type: string; title: string; url?: string; classification?: string };
type EvidenceSummary = { source_count: number; classifications: Record<string, number>; source_types: Record<string, number>; coverage_note: string };
type Message = { role: "user" | "assistant"; content: string; model?: string; provider?: string; sources?: Source[]; evidenceSummary?: EvidenceSummary; createdAt?: string };
type IntegrationStatus = { openai?: { configured?: boolean; model?: string }; ai?: { provider?: string; model?: string; configured?: boolean; web_search?: boolean; web_search_configured?: boolean; web_search_reachable?: boolean | null; web_search_status?: string } };
type AiResponse = { answer: string; model: string; provider?: string; sources?: Source[]; evidence_summary?: EvidenceSummary; conversation_id?: number; research_run_id?: number; workflow?: string; web_enabled?: boolean; web_configured?: boolean; web_status?: string };
type Conversation = { id: number; title: string; updated_at: string; messages: Array<{ role: "user" | "assistant"; content: string; model?: string; provider?: string; sources?: Source[]; created_at: string }> };
type Paginated<T> = { results?: T[] } | T[];
type PlatformPayload = { release: string; workflows: Array<{ key: string; label: string }>; source_inventory: Record<string, number | string>; governance: Record<string, boolean>; recent_runs: Array<{ id: number; conversation_id?: number; workflow: string; status: string; provider: string; model: string; source_count: number; created_at: string }> };

function StructuredAnswer({ content }: { content: string }) {
  const blocks = useMemo(() => content.split(/\n{2,}/).map((value) => value.trim()).filter(Boolean), [content]);
  return <div className="structured-ai-answer">{blocks.map((block, index) => {
    const lines = block.split("\n").map((value) => value.trim()).filter(Boolean);
    const first = lines[0]?.replace(/^#{1,6}\s*/, "").replace(/^\*\*(.+)\*\*:?$/, "$1");
    const heading = /^#{1,6}\s/.test(lines[0] ?? "") || /^\*\*.+\*\*:?$/.test(lines[0] ?? "") || (/^[A-Z][A-Za-z /&-]{2,48}:?$/.test(first ?? "") && lines.length > 1);
    const body = heading ? lines.slice(1) : lines;
    return <section className="ai-insight-card" key={`${index}-${first ?? "answer"}`}>
      {heading && <h3>{first?.replace(/:$/, "")}</h3>}
      <div>{body.map((line, lineIndex) => /^[-•*]\s+/.test(line)
        ? <div className="ai-bullet" key={lineIndex}><span /><p>{line.replace(/^[-•*]\s+/, "")}</p></div>
        : <p key={lineIndex}>{line}</p>)}</div>
    </section>;
  })}</div>;
}

export function AssistantWorkspace() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [workflow, setWorkflow] = useState("research");
  const [platform, setPlatform] = useState<PlatformPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [model, setModel] = useState("");
  const [provider, setProvider] = useState("openai");
  const [webConfigured, setWebConfigured] = useState(false);
  const [webReachable, setWebReachable] = useState<boolean | null>(null);
  const [webStatus, setWebStatus] = useState("disabled");
  const [copied, setCopied] = useState<number | null>(null);
  const threadRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  async function loadPlatformState() {
    const [conversationPayload, platformPayload] = await Promise.all([
      apiGet<Paginated<Conversation>>("/ai/conversations/"),
      apiGet<PlatformPayload>("/ai/platform/"),
    ]);
    setConversations(Array.isArray(conversationPayload) ? conversationPayload : conversationPayload.results ?? []);
    setPlatform(platformPayload);
  }

  useEffect(() => {
    let active = true;
    const timer = window.setTimeout(() => {
      void loadPlatformState().catch(() => { if (active) setPlatform(null); });
    }, 0);
    return () => { active = false; window.clearTimeout(timer); };
  }, []);

  useEffect(() => {
    let active = true;
    const loadStatus = async () => {
      try {
        const status = await apiGet<IntegrationStatus>("/integrations/status/?probe=true");
        if (!active) return;
        setConfigured(Boolean(status.ai?.configured ?? status.openai?.configured));
        setModel(status.ai?.model ?? status.openai?.model ?? "");
        setProvider(status.ai?.provider ?? "openai");
        setWebConfigured(Boolean(status.ai?.web_search_configured));
        setWebReachable(status.ai?.web_search_reachable ?? null);
        setWebStatus(status.ai?.web_search_status ?? "disabled");
      } catch {
        if (active) { setConfigured(null); setWebReachable(false); setWebStatus("unavailable"); }
      }
    };
    const start = window.setTimeout(() => void loadStatus(), 0);
    const timer = window.setInterval(() => void loadStatus(), 60000);
    return () => { active = false; window.clearTimeout(start); window.clearInterval(timer); };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || loading) return;
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, { role: "user", content: text, createdAt: new Date().toISOString() }]);
    setPrompt(""); setError(""); setLoading(true);
    try {
      const response = await apiPost<AiResponse>("/ai/chat/", { message: text, history, workflow, persist: true, conversation_id: conversationId });
      setMessages((current) => [...current, { role: "assistant", content: response.answer, model: response.model, provider: response.provider, sources: response.sources, evidenceSummary: response.evidence_summary, createdAt: new Date().toISOString() }]);
      if (response.conversation_id) setConversationId(response.conversation_id);
      setConfigured(true); setModel(response.model); setProvider(response.provider ?? provider);
      setWebConfigured(Boolean(response.web_configured)); setWebReachable(Boolean(response.web_enabled));
      setWebStatus(response.web_status ?? (response.web_enabled ? "live" : "unavailable"));
      void loadPlatformState().catch(() => undefined);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "ForgeGov AI could not complete the request.");
    } finally { setLoading(false); }
  }

  async function copyMessage(index: number, content: string) {
    await navigator.clipboard.writeText(content);
    setCopied(index);
    window.setTimeout(() => setCopied(null), 1600);
  }

  function startNewResearch() {
    setMessages([]); setConversationId(null); setError("");
  }

  function resumeConversation(conversation: Conversation) {
    setConversationId(conversation.id);
    setMessages(conversation.messages.map((message) => ({
      role: message.role,
      content: message.content,
      model: message.model,
      provider: message.provider,
      sources: message.sources,
      createdAt: message.created_at,
    })));
    setError("");
  }

  const webLabel =
    webStatus === "live" || webReachable
      ? "Live Web Connected"
      : webStatus === "degraded"
        ? "Live Web Degraded"
        : webStatus === "unavailable"
          ? "Live Web Unavailable"
          : webConfigured
            ? "Live Web Configured"
            : "Live Web Not Configured";
  const webDetail =
    webStatus === "live" || webReachable
      ? "ForgeGov private SearXNG search is connected."
      : webStatus === "degraded"
        ? "The live service is recovering; cached web intelligence may be used when available."
        : webStatus === "unavailable"
          ? "Live web is unavailable. Government connectors and stored ForgeGov intelligence remain active."
          : webConfigured
            ? "The private live-web service is configured and awaiting a successful health probe."
            : "Provision the ForgeGov private SearXNG service or configure SEARXNG_URL.";

  return <div className="assistant-layout modern-ai-layout">
    <section className="assistant-main">
      <header className="assistant-heading"><span className="assistant-mark"><Sparkles size={24} /></span><div><span className="eyebrow">FORGEAI INTELLIGENCE PLATFORM · v3.2.6</span><h1>ForgeGov AI</h1><p>Grounded research across opportunities, awards, capture, proposals, company evidence, and authorized workspace records.</p></div><div className="ai-heading-actions"><div className="ai-mode-badges"><span>{provider === "ollama" ? "Open-source model" : "Hosted model"}</span><span className={webStatus === "live" || webReachable ? "live" : webStatus === "degraded" || webStatus === "unavailable" ? "reconnecting" : "pending"}>{webLabel}</span></div>{messages.length > 0 && <button className="ai-clear-button" type="button" onClick={startNewResearch}><Plus size={15}/> New research</button>}</div></header>
      {!messages.length ? <div className="assistant-empty"><div className="ai-orb"><Bot size={36} /></div><h2>What are you working on?</h2><p>Start with an opportunity, a capture decision, a teaming gap, or a market question. The assistant will lead with the answer and show evidence separately.</p><div className="prompt-grid">{prompts.map((item) => { const Icon = item.icon; return <button key={item.title} onClick={() => setPrompt(item.text)}><Icon size={20} /><strong>{item.title}</strong><span>{item.text}</span></button>; })}</div></div>
        : <div className="chat-thread" ref={threadRef}>{messages.map((message, index) => <article key={`${message.createdAt ?? index}-${index}`} className={`chat-message ${message.role}`}><header><strong>{message.role === "user" ? "You" : "ForgeGov AI"}</strong><div>{message.createdAt && <time>{new Date(message.createdAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</time>}{message.role === "assistant" && <button type="button" onClick={() => void copyMessage(index, message.content)} aria-label="Copy answer">{copied === index ? <Check size={14}/> : <Clipboard size={14}/>}</button>}</div></header>{message.role === "assistant" ? <StructuredAnswer content={message.content} /> : <p>{message.content}</p>}{message.evidenceSummary && <div className="ai-evidence-summary"><ShieldCheck size={15}/><span>{message.evidenceSummary.source_count} source records supplied</span><small>{message.evidenceSummary.coverage_note}</small></div>}{message.sources?.length ? <details className="ai-source-list"><summary>Evidence and provenance ({message.sources.length})</summary>{message.sources.slice(0, 18).map((source) => source.url ? <a key={`${source.label}-${source.url}`} href={source.url} target="_blank" rel="noreferrer"><b>{source.label}</b><span>{source.title}<small>{source.classification?.replaceAll("_", " ")}</small></span><ExternalLink size={12} /></a> : <div key={`${source.label}-${source.title}`}><b>{source.label}</b><span>{source.title}<small>{source.classification?.replaceAll("_", " ")}</small></span></div>)}</details> : null}</article>)}{loading && <div className="chat-message assistant"><strong>ForgeGov AI</strong><p className="ai-thinking"><LoaderCircle className="spin" size={17} /> Reviewing authorized records and available live sources…</p></div>}</div>}
      {error && <p className="assistant-error">{error}</p>}
      <form className="assistant-composer" onSubmit={submit}><label className="ai-workflow-select"><span>Research workflow</span><select value={workflow} onChange={(event) => setWorkflow(event.target.value)} disabled={loading}>{(platform?.workflows ?? [{key:"research",label:"Research"},{key:"opportunity",label:"Opportunity"},{key:"capture",label:"Capture"},{key:"proposal",label:"Proposal"},{key:"market",label:"Market"}]).map((item)=><option key={item.key} value={item.key}>{item.label}</option>)}</select></label><textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }} placeholder="Ask about an opportunity, agency, competitor, clause, partner, risk, or next action…" disabled={loading} maxLength={50000} /><div><span><ShieldCheck size={15} /> Evidence is assistance, not approval · Enter to send</span><button type="submit" aria-label="Send" disabled={loading || !prompt.trim()}>{loading ? <LoaderCircle className="spin" size={18} /> : <ArrowUp size={18} />}</button></div></form>
    </section>
    <aside className="assistant-context"><span className="eyebrow">ACTIVE CONTEXT</span><h2>Research sources</h2><div className="context-source"><span className={`status-dot ${configured ? "live" : "pending"}`} /><div><strong>{provider === "ollama" ? "Self-hosted Ollama" : "OpenAI API"}</strong><small>{configured ? `${model || "Configured model"} configured` : "Provider needs configuration"}</small></div></div><div className="context-source"><span className={`status-dot ${webStatus === "live" || webReachable ? "live" : webStatus === "degraded" || webStatus === "unavailable" ? "reconnecting" : "pending"}`} /><div><strong>Live web research</strong><small>{webDetail}</small></div></div><div className="context-source"><span className="status-dot live" /><div><strong>ForgeGov workspace</strong><small>Company profile, pipeline, capture plans, proposals, tasks, contacts, and files</small></div></div><div className="context-source"><span className="status-dot live" /><div><strong>Government records</strong><small>SAM.gov, Grants.gov, USAspending, and available stored public records</small></div></div><div className="context-warning"><ShieldCheck size={18} /><p>Private organization data stays scoped to authorized workspace access. Source counts do not prove completeness, correctness, readiness, or approval.</p></div>{conversations.length>0&&<section className="ai-history"><div><History size={16}/><strong>Research history</strong></div>{conversations.slice(0,8).map((conversation)=><button type="button" className={conversation.id===conversationId?"selected":""} key={conversation.id} onClick={()=>resumeConversation(conversation)}><span>{conversation.title}</span><small>{new Date(conversation.updated_at).toLocaleDateString()}</small></button>)}</section>}</aside>
  </div>;
}
