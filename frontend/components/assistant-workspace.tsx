"use client";

import { FormEvent, useEffect, useState } from "react";
import { ArrowUp, Bot, FileSearch, LoaderCircle, Search, ShieldCheck, Sparkles, Target, Users } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

const prompts = [
  { icon: FileSearch, title: "Summarize recent opportunities", text: "Review current stored opportunities, deadlines, requirements, and capture risks." },
  { icon: Target, title: "Run a bid/no-bid review", text: "Score strategic fit, eligibility, timing, competition, and capture risk." },
  { icon: Users, title: "Find teaming gaps", text: "Compare pipeline requirements against current pursuits, contacts, and partner needs." },
  { icon: Search, title: "Research my active pipeline", text: "Review active pipeline items, next actions, deadlines, and missing information." },
];

type Message = { role: "user" | "assistant"; content: string; model?: string };
type IntegrationStatus = { openai?: { configured?: boolean; model?: string } };
type AiResponse = {
  answer: string;
  model: string;
  response_id?: string;
  request_id?: string;
  sources?: Array<{ label: string; type: string; title: string; url?: string }>;
};

export function AssistantWorkspace() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [configured, setConfigured] = useState<boolean | null>(null);
  const [model, setModel] = useState("");
  const [sourceCount, setSourceCount] = useState(0);

  useEffect(() => {
    let active = true;
    apiGet<IntegrationStatus>("/integrations/status/")
      .then((status) => {
        if (!active) return;
        setConfigured(Boolean(status.openai?.configured));
        setModel(status.openai?.model ?? "");
      })
      .catch(() => {
        if (active) setConfigured(null);
      });
    return () => { active = false; };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text || loading) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    const userMessage: Message = { role: "user", content: text };
    setMessages((current) => [...current, userMessage]);
    setPrompt("");
    setError("");
    setLoading(true);

    try {
      const response = await apiPost<AiResponse>("/ai/chat/", { message: text, history });
      setMessages((current) => [...current, { role: "assistant", content: response.answer, model: response.model }]);
      setConfigured(true);
      setModel(response.model);
      setSourceCount(response.sources?.length ?? 0);
    } catch (submitError) {
      const message = submitError instanceof Error ? submitError.message : "ForgeGov AI could not complete the request.";
      setError(message);
      setMessages((current) => [...current, { role: "assistant", content: `I could not complete that request. ${message}` }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="assistant-layout">
      <section className="assistant-main">
        <div className="assistant-heading">
          <span className="assistant-mark"><Sparkles size={24} /></span>
          <div>
            <span className="eyebrow">Grounded government contracting AI</span>
            <h1>ForgeGov AI</h1>
            <p>Ask questions across recent opportunities, awards, pipeline records, pursuits, tasks, contacts, and file metadata.</p>
          </div>
        </div>
        {!messages.length ? (
          <div className="assistant-empty">
            <div className="ai-orb"><Bot size={36} /></div>
            <h2>What should we work on?</h2>
            <p>Choose a workflow or ask a government-contracting question. ForgeGov sends the request from the backend and grounds record-specific facts in your workspace data.</p>
            <div className="prompt-grid">
              {prompts.map((item) => {
                const Icon = item.icon;
                return <button key={item.title} onClick={() => setPrompt(item.title)}><Icon size={20} /><strong>{item.title}</strong><span>{item.text}</span></button>;
              })}
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((message, index) => (
              <div key={index} className={`chat-message ${message.role}`}>
                <strong>{message.role === "user" ? "You" : "ForgeGov AI"}</strong>
                <p>{message.content}</p>
                {message.model && <small>Model: {message.model}</small>}
              </div>
            ))}
            {loading && <div className="chat-message assistant"><strong>ForgeGov AI</strong><p className="ai-thinking"><LoaderCircle className="spin" size={17} /> Reviewing grounded workspace records…</p></div>}
          </div>
        )}
        {error && <p className="assistant-error">{error}</p>}
        <form className="assistant-composer" onSubmit={submit}>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask ForgeGov about an opportunity, agency, competitor, pursuit, or capture action..." disabled={loading} maxLength={8000} />
          <div><span><ShieldCheck size={15} /> Grounded answers with record labels</span><button type="submit" aria-label="Send" disabled={loading || !prompt.trim()}>{loading ? <LoaderCircle className="spin" size={18} /> : <ArrowUp size={18} />}</button></div>
        </form>
      </section>
      <aside className="assistant-context">
        <span className="eyebrow">Research context</span><h2>Sources available</h2>
        <div className="context-source"><span className={`status-dot ${configured ? "live" : "pending"}`} /><div><strong>OpenAI API</strong><small>{configured === true ? `${model || "Configured model"} ready` : configured === false ? "Key not detected by backend" : "Checking configuration"}</small></div></div>
        <div className="context-source"><span className="status-dot live" /><div><strong>ForgeGov workspace</strong><small>Pipeline, pursuits, tasks, contacts, files</small></div></div>
        <div className="context-source"><span className="status-dot live" /><div><strong>Government data</strong><small>Stored SAM.gov, Grants.gov, and USAspending records</small></div></div>
        <div className="context-source"><span className="status-dot live" /><div><strong>Last answer context</strong><small>{sourceCount ? `${sourceCount} records supplied` : "Loaded when you submit a request"}</small></div></div>
        <div className="context-warning"><ShieldCheck size={18} /><p>ForgeGov will not invent deadlines, certifications, contacts, award values, or requirements when source records are missing.</p></div>
      </aside>
    </div>
  );
}
