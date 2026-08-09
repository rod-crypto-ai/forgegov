"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Archive,
  CheckCircle2,
  Download,
  FileCheck2,
  LoaderCircle,
  RefreshCw,
  Send,
  Trophy,
  XCircle,
} from "lucide-react";
import { API_BASE, apiGet, apiPost } from "@/lib/api";

type Snapshot = {
  id: number;
  sequence: number;
  submitted_at: string;
  submitted_by: string;
  delivery_method: string;
  confirmation_reference: string;
  snapshot_hash: string;
  file_count: number;
};

type Payload = {
  plan: {
    id: number;
    status: string;
    submission_method: string;
    final_submission_verified: boolean;
  };
  submission_readiness: {
    ready: boolean;
    blockers: string[];
    file_count: number;
    deadline?: string | null;
  };
  snapshots: Snapshot[];
  closeout: {
    id: number;
    status: string;
    awardee: string;
    award_value?: string | number | null;
    award_date?: string | null;
    debrief_requested: boolean;
    debrief_received: boolean;
    win_loss_reason: string;
    customer_feedback: string;
    strengths: string[];
    weaknesses: string[];
    lessons_learned: string[];
  };
  exports: Array<{format:string;label:string}>;
  warning: string;
};

const closeoutStatuses = ["submitted", "evaluation", "discussions", "fpr", "awarded", "lost", "cancelled"];

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function SubmissionControl({ noticeId }: { noticeId: string }) {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [notes, setNotes] = useState("");

  const base = `/ai/opportunities/${encodeURIComponent(noticeId)}`;

  const load = useCallback(async () => {
    setData(await apiGet<Payload>(`${base}/submission-control/`));
  }, [base]);

  useEffect(() => {
    let cancelled = false;
    apiGet<Payload>(`${base}/submission-control/`)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((error: unknown) => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Submission Control could not be loaded.");
      });
    return () => {
      cancelled = true;
    };
  }, [base]);

  const submitted = useMemo(() => Boolean(data?.snapshots.length), [data]);

  async function createSnapshot() {
    setBusy("submit");
    setMessage("");
    try {
      const result = await apiPost<Payload>(`${base}/submission-control/`, {
        action: "submit",
        confirmation_reference: confirmation,
        notes,
      });
      setData(result);
      setConfirmation("");
      setNotes("");
      setMessage("Immutable submission snapshot created.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Submission snapshot could not be created.");
    } finally {
      setBusy("");
    }
  }

  async function updateCloseout(patch: Record<string, unknown>) {
    setBusy("closeout");
    try {
      setData(await apiPost<Payload>(`${base}/submission-control/`, { action: "update_closeout", ...patch }));
      setMessage("Post-submission record updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Closeout could not be updated.");
    } finally {
      setBusy("");
    }
  }

  if (!data) {
    return (
      <section className="data-panel proposal-loading">
        <LoaderCircle className="spin" />
        <strong>Loading Submission Control</strong>
        {message && <p>{message}</p>}
      </section>
    );
  }

  return (
    <section className="submission-control-shell">
      <header className="proposal-command-header">
        <div>
          <span className="eyebrow">SUBMISSION CONTROL + PROPOSAL CLOSEOUT</span>
          <h2>Freeze what was submitted and preserve the outcome</h2>
          <p>Final readiness, delivery evidence, immutable submission history, exports, evaluation status, debriefs, and lessons learned stay attached to this pursuit.</p>
        </div>
        <button className="secondary-button" onClick={() => void load()} disabled={Boolean(busy)}>
          <RefreshCw size={16}/> Refresh
        </button>
      </header>

      {message && <p className="inline-message">{message}</p>}

      <div className="proposal-kpis">
        <article>
          <span>Submission gate</span>
          <strong>{data.submission_readiness.ready ? "READY" : "BLOCKED"}</strong>
          <small>{data.submission_readiness.blockers.length} blockers</small>
        </article>
        <article>
          <span>Final files</span>
          <strong>{data.submission_readiness.file_count}</strong>
          <small>registered manifest entries</small>
        </article>
        <article>
          <span>Submission snapshots</span>
          <strong>{data.snapshots.length}</strong>
          <small>immutable historical records</small>
        </article>
        <article>
          <span>Lifecycle</span>
          <strong>{label(data.closeout.status)}</strong>
          <small>{submitted ? "post-submission tracking active" : "awaiting submission"}</small>
        </article>
      </div>

      {!data.submission_readiness.ready && (
        <section className="data-panel submission-blockers">
          <div className="panel-title-row">
            <div><span className="eyebrow">FINAL GATE</span><h3>Submission blockers</h3></div>
            <XCircle/>
          </div>
          {data.submission_readiness.blockers.map((row, index) => <p key={index}>• {row}</p>)}
        </section>
      )}

      <div className="proposal-execution-grid">
        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">SUBMIT + FREEZE</span><h3>Create immutable submission record</h3></div>
            <Send/>
          </div>
          <p>Only use this after the official submission has been sent. ForgeGov records the current requirements, reviews, findings, amendment baseline, and file manifest.</p>
          <label className="proposal-field">
            <span>Official confirmation / receipt reference</span>
            <input value={confirmation} onChange={(e)=>setConfirmation(e.target.value)} placeholder="Portal receipt, confirmation ID, or email reference"/>
          </label>
          <label className="proposal-field">
            <span>Submission notes</span>
            <textarea value={notes} onChange={(e)=>setNotes(e.target.value)} placeholder="Delivery notes, exceptions, or final verification context"/>
          </label>
          <button className="primary-button" disabled={!data.submission_readiness.ready || busy==="submit"} onClick={()=>void createSnapshot()}>
            <FileCheck2 size={16}/> {busy==="submit" ? "Creating snapshot…" : "Record official submission"}
          </button>
        </section>

        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">EXECUTIVE EXPORTS</span><h3>Download current proposal intelligence</h3></div>
            <Download/>
          </div>
          <div className="submission-export-list">
            {data.exports.map((row)=>(
              <a key={row.format} className="secondary-button" href={`${API_BASE}${base}/submission-exports/${row.format}/`}>
                <Download size={15}/>{row.label}
              </a>
            ))}
          </div>
          <p className="muted-copy">Exports reflect the current workspace. The immutable submission snapshot is the authoritative ForgeGov historical record after submission.</p>
        </section>
      </div>

      <section className="data-panel">
        <div className="panel-title-row">
          <div><span className="eyebrow">SUBMISSION HISTORY</span><h3>Immutable snapshots</h3></div>
          <Archive/>
        </div>
        <div className="submission-history-list">
          {data.snapshots.length ? data.snapshots.map((row)=>(
            <article key={row.id}>
              <div><strong>Submission #{row.sequence}</strong><p>{new Date(row.submitted_at).toLocaleString()}</p></div>
              <div><span>{row.delivery_method || "Method not recorded"}</span><small>{row.file_count} files · {row.submitted_by || "Unknown user"}</small></div>
              <div><span>{row.confirmation_reference || "No confirmation reference"}</span><small>SHA-256 {row.snapshot_hash.slice(0,16)}…</small></div>
            </article>
          )) : <p>No official submission has been recorded yet.</p>}
        </div>
      </section>

      <section className="data-panel">
        <div className="panel-title-row">
          <div><span className="eyebrow">POST-SUBMISSION</span><h3>Award, debrief, and lessons learned</h3></div>
          <Trophy/>
        </div>
        <div className="submission-closeout-grid">
          <label><span>Status</span><select value={data.closeout.status} onChange={(e)=>void updateCloseout({status:e.target.value})}>{closeoutStatuses.map((s)=><option key={s} value={s}>{label(s)}</option>)}</select></label>
          <label><span>Awardee</span><input defaultValue={data.closeout.awardee} onBlur={(e)=>void updateCloseout({awardee:e.target.value})}/></label>
          <label><span>Award value</span><input type="number" defaultValue={data.closeout.award_value == null ? "" : String(data.closeout.award_value)} onBlur={(e)=>void updateCloseout({award_value:e.target.value})}/></label>
          <label><span>Award date</span><input type="date" defaultValue={data.closeout.award_date || ""} onBlur={(e)=>void updateCloseout({award_date:e.target.value || null})}/></label>
        </div>
        <div className="submission-closeout-checks">
          <label><input type="checkbox" checked={data.closeout.debrief_requested} onChange={(e)=>void updateCloseout({debrief_requested:e.target.checked})}/> Debrief requested</label>
          <label><input type="checkbox" checked={data.closeout.debrief_received} onChange={(e)=>void updateCloseout({debrief_received:e.target.checked})}/> Debrief received</label>
        </div>
        <label className="proposal-field"><span>Win / loss reason</span><textarea defaultValue={data.closeout.win_loss_reason} onBlur={(e)=>void updateCloseout({win_loss_reason:e.target.value})}/></label>
        <label className="proposal-field"><span>Customer feedback</span><textarea defaultValue={data.closeout.customer_feedback} onBlur={(e)=>void updateCloseout({customer_feedback:e.target.value})}/></label>
        <label className="proposal-field"><span>Strengths identified</span><textarea defaultValue={(data.closeout.strengths || []).join("\n")} onBlur={(e)=>void updateCloseout({strengths:e.target.value.split("\n").map(v=>v.trim()).filter(Boolean)})}/></label>
        <label className="proposal-field"><span>Weaknesses / gaps</span><textarea defaultValue={(data.closeout.weaknesses || []).join("\n")} onBlur={(e)=>void updateCloseout({weaknesses:e.target.value.split("\n").map(v=>v.trim()).filter(Boolean)})}/></label>
        <label className="proposal-field"><span>Lessons learned</span><textarea defaultValue={(data.closeout.lessons_learned || []).join("\n")} onBlur={(e)=>void updateCloseout({lessons_learned:e.target.value.split("\n").map(v=>v.trim()).filter(Boolean)})}/></label>
        <p className="muted-copy"><CheckCircle2 size={14}/> Closeout knowledge remains inside the company workspace and can feed future capture analysis.</p>
      </section>

      <p className="proposal-boundary-note">{data.warning}</p>
    </section>
  );
}
