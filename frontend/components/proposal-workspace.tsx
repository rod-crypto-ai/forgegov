"use client";
import {useCallback,useEffect,useState} from "react";
import {AlertTriangle,CheckCircle2,ClipboardCheck,FileText,LoaderCircle,RefreshCw,ShieldCheck} from "lucide-react";
import {apiGet} from "@/lib/api";

type Requirement={id:string;requirement:string;source:string;status:string;owner:string;evidence:string;source_kind:string};
type Payload={generated_at:string;readiness:{score:number;document_score:number;completed_requirements:number;total_requirements:number};compliance_matrix:Requirement[];proposal_outline:{title:string;basis:string;status:string}[];review_plan:{name:string;target_at:string;status:string}[];submission_checklist:{label:string;complete:boolean}[];proposal_tasks:{id:number;title:string;completed:boolean;due_at?:string|null;assigned_to:string}[];alerts:string[];evidence_summary:{ready_documents:number;clins:number;clauses:number;deliverables:number};warning:string};
export function ProposalWorkspace({noticeId}:{noticeId:string}){
 const[data,setData]=useState<Payload|null>(null);const[busy,setBusy]=useState(true);const[message,setMessage]=useState("");
 const load=useCallback(async()=>{setBusy(true);try{setData(await apiGet<Payload>(`/ai/opportunities/${encodeURIComponent(noticeId)}/proposal-workspace/`));setMessage("")}catch(e){setMessage(e instanceof Error?e.message:"Proposal workspace could not be loaded")}finally{setBusy(false)}},[noticeId]);
 useEffect(() => {
  let cancelled = false;

  apiGet<Payload>(
    `/ai/opportunities/${encodeURIComponent(noticeId)}/proposal-workspace/`
  )
    .then((result) => {
      if (!cancelled) {
        setData(result);
        setMessage("");
        setBusy(false);
      }
    })
    .catch((error: unknown) => {
      if (!cancelled) {
        setMessage(
          error instanceof Error
            ? error.message
            : "Proposal workspace could not be loaded"
        );
        setBusy(false);
      }
    });

  return () => {
    cancelled = true;
  };
}, [noticeId]);
 if(!data)return <section className="data-panel proposal-loading">{busy?<><LoaderCircle className="spin"/><strong>Building proposal workspace</strong></>:<><AlertTriangle/><strong>Proposal workspace unavailable</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></>}</section>;
 return <section className="proposal-command-shell">
  <header className="proposal-command-header"><div><span className="eyebrow">PROPOSAL + COMPLIANCE COMMAND CENTER</span><h2>Turn capture evidence into an executable response plan</h2><p>Compliance, outline, reviews, submission readiness, and proposal work are grounded in the indexed solicitation and your ForgeGov workspace.</p></div><button className="secondary-button" onClick={()=>void load()} disabled={busy}><RefreshCw size={16}/> Refresh</button></header>
  {data.alerts.length>0&&<div className="proposal-alerts">{data.alerts.map((a,i)=><p key={i}><AlertTriangle size={15}/>{a}</p>)}</div>}
  <div className="proposal-kpis"><article><span>Proposal readiness</span><strong>{data.readiness.score}%</strong><small>{data.readiness.completed_requirements}/{data.readiness.total_requirements} evidence checks</small></article><article><span>Document evidence</span><strong>{data.readiness.document_score}%</strong><small>{data.evidence_summary.ready_documents} indexed documents</small></article><article><span>CLIN signals</span><strong>{data.evidence_summary.clins}</strong><small>{data.evidence_summary.deliverables} deliverable signals</small></article><article><span>Clause signals</span><strong>{data.evidence_summary.clauses}</strong><small>FAR / DFARS evidence</small></article></div>
  <div className="proposal-grid"><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">COMPLIANCE MATRIX</span><h3>Requirement coverage</h3></div><ClipboardCheck/></div><div className="proposal-matrix">{data.compliance_matrix.map(r=><article key={r.id} className={`proposal-status-${r.status}`}><span>{r.status.replaceAll("_"," ")}</span><div><strong>{r.requirement}</strong><p>{r.evidence}</p><small>{r.source}</small></div></article>)}</div></section>
  <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PROPOSAL OUTLINE</span><h3>Response structure</h3></div><FileText/></div><div className="proposal-outline">{data.proposal_outline.map((r,i)=><article key={i}><strong>{r.title}</strong><p>{r.basis}</p><span>{r.status.replaceAll("_"," ")}</span></article>)}</div></section></div>
  <div className="proposal-grid"><section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">COLOR REVIEWS</span><h3>Review plan</h3></div><ShieldCheck/></div><div className="proposal-review-list">{data.review_plan.length?data.review_plan.map((r,i)=><article key={i}><strong>{r.name}</strong><span>{new Date(r.target_at).toLocaleString()}</span><small>{r.status}</small></article>):<p>No response deadline is available to calculate review targets.</p>}</div></section>
  <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">SUBMISSION GATE</span><h3>Final readiness</h3></div><CheckCircle2/></div><div className="proposal-checklist">{data.submission_checklist.map((r,i)=><p key={i}>{r.complete?<CheckCircle2 size={16}/>:<AlertTriangle size={16}/>}<span>{r.label}</span></p>)}</div></section></div>
  <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PROPOSAL WORK</span><h3>Assigned tasks</h3></div><small>{data.proposal_tasks.filter(t=>!t.completed).length} open</small></div><div className="proposal-task-grid">{data.proposal_tasks.length?data.proposal_tasks.map(t=><article key={t.id} className={t.completed?"complete":""}><strong>{t.title}</strong><p>{t.assigned_to||"Unassigned"}</p><small>{t.due_at?new Date(t.due_at).toLocaleString():"No due date"}</small></article>):<p>No proposal tasks are linked to this pursuit yet.</p>}</div></section>
  <p className="proposal-warning">{data.warning}</p>
 </section>
}
