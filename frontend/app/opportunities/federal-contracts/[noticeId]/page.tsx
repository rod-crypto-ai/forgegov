"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Building2, ExternalLink, FileText, LoaderCircle, Target } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet, apiPost } from "@/lib/api";

type DocumentRow = { name: string; url: string; preview_available?: boolean };
type IncumbentSignal = { recipient_name: string; recipient_uei?: string; award_count: number; obligated: number; latest_end?: string | null };
type Detail = {
  opportunity: Record<string, unknown>;
  description: string;
  documents: DocumentRow[];
  source_url: string;
  incumbent_signals?: IncumbentSignal[];
  incumbent_signal_note?: string;
};

function value(row: Record<string, unknown>, key: string) {
  const item = row[key];
  return item === null || item === undefined || item === "" ? "—" : String(item);
}

export default function FederalOpportunityDetailPage() {
  const params = useParams<{ noticeId: string }>();
  const noticeId = decodeURIComponent(params.noticeId);
  const [data, setData] = useState<Detail | null>(null);
  const [message, setMessage] = useState("Loading SAM.gov opportunity details and documents…");
  const [adding, setAdding] = useState(false);

  const load = useCallback(async () => {
    try {
      const result = await apiGet<Detail>(`/live/sam/opportunities/${encodeURIComponent(noticeId)}/`);
      setData(result);
      setMessage(`${result.documents?.length ?? 0} public documents loaded.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Opportunity detail could not be loaded");
    }
  }, [noticeId]);

  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function addToPipeline() {
    setAdding(true);
    try {
      await apiPost("/workflow/opportunity-to-pipeline/", { source_id: noticeId, stage: "reviewing" });
      setMessage("Opportunity added to the capture pipeline.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Opportunity could not be added");
    } finally { setAdding(false); }
  }

  const opportunity = data?.opportunity ?? {};
  return <>
    <header className="feature-hero opportunity-detail-hero">
      <div>
        <Link className="detail-back" href="/opportunities/federal-contracts"><ArrowLeft size={16}/> Back to search</Link>
        <span className="eyebrow">SAM.gov opportunity intelligence</span>
        <h1>{value(opportunity, "title")}</h1>
        <p>{value(opportunity, "fullParentPathName")}</p>
      </div>
      <div className="detail-actions">
        {data?.source_url ? <a className="secondary-button" href={data.source_url} target="_blank" rel="noreferrer">SAM.gov <ExternalLink size={16}/></a> : null}
        <button className="primary-button" onClick={() => void addToPipeline()} disabled={adding}><Target size={16}/>{adding ? "Adding…" : "Add to pipeline"}</button>
      </div>
    </header>
    <p className="inline-message">{message}</p>
    {!data ? <div className="table-state"><LoaderCircle className="spin"/><strong>Loading opportunity</strong></div> : <>
      <section className="insight-strip detail-facts">
        <div><span>Solicitation</span><strong>{value(opportunity, "solicitationNumber")}</strong></div>
        <div><span>Notice type</span><strong>{value(opportunity, "type")}</strong></div>
        <div><span>NAICS</span><strong>{value(opportunity, "naicsCode")}</strong></div>
        <div><span>Deadline</span><strong>{value(opportunity, "responseDeadLine")}</strong></div>
      </section>
      <div className="split-intelligence">
        <section className="data-panel opportunity-description"><div className="panel-title-row"><div><span className="eyebrow">REQUIREMENT</span><h2>Description</h2></div></div><div className="rich-description">{data.description || "SAM.gov did not return a public description through the API."}</div></section>
        <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">FILES</span><h2>Government documents</h2></div><small>{data.documents.length} files</small></div><div className="document-list">{data.documents.length ? data.documents.map((document, index)=><a key={`${document.url}-${index}`} href={document.url} target="_blank" rel="noreferrer"><FileText/><span><strong>{document.name}</strong><small>{document.preview_available ? "PDF preview available" : "Open source file"}</small></span><ExternalLink size={16}/></a>) : <div className="table-state"><FileText/><strong>No public attachments returned</strong></div>}</div></section>
      </div>
      <section className="data-panel incumbent-panel"><div className="panel-title-row"><div><span className="eyebrow">MARKET EVIDENCE</span><h2>Incumbent signals</h2></div><small>{data.incumbent_signals?.length ?? 0} candidates</small></div><p className="panel-note">{data.incumbent_signal_note}</p><div className="intelligence-list">{data.incumbent_signals?.length ? data.incumbent_signals.map((signal, index)=><article key={`${signal.recipient_name}-${index}`}><Building2/><div><span>Potential incumbent / competitor signal</span><h3>{signal.recipient_name}</h3><p>{signal.award_count.toLocaleString()} matching stored awards · {new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(signal.obligated ?? 0))} obligated</p><small>{signal.recipient_uei ? `UEI ${signal.recipient_uei}` : "UEI unavailable"}{signal.latest_end ? ` · Latest end ${signal.latest_end}` : ""}</small></div></article>) : <div className="table-state"><Building2/><strong>Load USAspending award data to generate incumbent signals</strong></div>}</div></section>
    </>}
  </>;
}
