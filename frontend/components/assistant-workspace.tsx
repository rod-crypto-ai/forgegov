"use client";

import { FormEvent, useState } from "react";
import { ArrowUp, Bot, FileSearch, Search, ShieldCheck, Sparkles, Target, Users } from "lucide-react";

const prompts = [
  { icon: FileSearch, title: "Summarize a solicitation", text: "Extract deadlines, requirements, evaluation criteria, and submission instructions." },
  { icon: Target, title: "Run a bid/no-bid review", text: "Score strategic fit, eligibility, timing, competition, and capture risk." },
  { icon: Users, title: "Find teaming gaps", text: "Compare requirements against company capabilities and identify partner needs." },
  { icon: Search, title: "Research an agency", text: "Review awards, incumbents, categories, buying offices, and upcoming work." },
];

export function AssistantWorkspace() {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<Array<{ role: "user" | "assistant"; content: string }>>([]);

  function submit(event: FormEvent) {
    event.preventDefault();
    const text = prompt.trim();
    if (!text) return;
    setMessages((current) => [
      ...current,
      { role: "user", content: text },
      { role: "assistant", content: "The AI execution service is not configured yet. ForgeGov saved the requested workflow in the interface, but it will not fabricate an answer without a connected model and grounded source records." },
    ]);
    setPrompt("");
  }

  return (
    <div className="assistant-layout">
      <section className="assistant-main">
        <div className="assistant-heading"><span className="assistant-mark"><Sparkles size={24} /></span><div><span className="eyebrow">Grounded government contracting AI</span><h1>ForgeGov AI</h1><p>Ask questions across opportunities, awards, vendors, agencies, contacts, pursuits, and uploaded files.</p></div></div>
        {!messages.length ? (
          <div className="assistant-empty">
            <div className="ai-orb"><Bot size={36} /></div>
            <h2>What should we work on?</h2>
            <p>Choose a workflow or ask a government-contracting question. Production answers will cite the records and files used.</p>
            <div className="prompt-grid">
              {prompts.map((item) => {
                const Icon = item.icon;
                return <button key={item.title} onClick={() => setPrompt(item.title)}><Icon size={20} /><strong>{item.title}</strong><span>{item.text}</span></button>;
              })}
            </div>
          </div>
        ) : (
          <div className="chat-thread">
            {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}><strong>{message.role === "user" ? "You" : "ForgeGov AI"}</strong><p>{message.content}</p></div>)}
          </div>
        )}
        <form className="assistant-composer" onSubmit={submit}>
          <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask ForgeGov about a solicitation, agency, competitor, pursuit, or uploaded file..." />
          <div><span><ShieldCheck size={15} /> Grounded answers with citations</span><button type="submit" aria-label="Send"><ArrowUp size={18} /></button></div>
        </form>
      </section>
      <aside className="assistant-context">
        <span className="eyebrow">Research context</span><h2>Sources available</h2>
        <div className="context-source"><span className="status-dot live" /><div><strong>ForgeGov workspace</strong><small>Pipeline, tasks, contacts, files</small></div></div>
        <div className="context-source"><span className="status-dot live" /><div><strong>SAM.gov</strong><small>Stored and live opportunities</small></div></div>
        <div className="context-source"><span className="status-dot pending" /><div><strong>USAspending</strong><small>Award research connector</small></div></div>
        <div className="context-source"><span className="status-dot pending" /><div><strong>Uploaded documents</strong><small>Document extraction planned</small></div></div>
        <div className="context-warning"><ShieldCheck size={18} /><p>ForgeGov will not invent deadlines, certifications, contacts, or requirements when the source data is missing.</p></div>
      </aside>
    </div>
  );
}
