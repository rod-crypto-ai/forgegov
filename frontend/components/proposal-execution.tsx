"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  Flag,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Users,
} from "lucide-react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";

type Member = { user_id: number; name: string; role: string };
type Requirement = {
  id: number;
  key: string;
  requirement: string;
  source: string;
  source_kind: string;
  evidence: string;
  status: string;
  owner_id?: number | null;
  owner: string;
  due_at?: string | null;
  notes: string;
  open_findings: number;
};
type Review = {
  id: number;
  review_type: string;
  label: string;
  target_at?: string | null;
  status: string;
  owner_id?: number | null;
  owner: string;
  completed_at?: string | null;
  summary: string;
  open_findings: number;
};
type Finding = {
  id: number;
  review_id?: number | null;
  requirement_id?: number | null;
  severity: string;
  title: string;
  detail: string;
  status: string;
  owner_id?: number | null;
  owner: string;
  due_at?: string | null;
};
type Payload = {
  plan: {
    id: number;
    status: string;
    submission_method: string;
    final_submission_verified: boolean;
    submission_ready: boolean;
    readiness_score: number;
  };
  requirements: Requirement[];
  reviews: Review[];
  findings: Finding[];
  members: Member[];
  amendment_impact: {
    changed: boolean;
    changes: string[];
    checked_at?: string | null;
  };
  project_room_tasks: Array<{
    id: number;
    title: string;
    status: string;
    priority: string;
    assigned_to: string;
    due_date?: string | null;
    source: string;
  }>;
  counts: {
    requirements_total: number;
    requirements_closed: number;
    reviews_total: number;
    reviews_passed: number;
    open_findings: number;
    critical_open_findings: number;
  };
  warning: string;
};

const requirementStatuses = ["needs_review", "open", "in_progress", "compliant", "not_applicable"];
const reviewStatuses = ["planned", "in_progress", "passed", "blocked"];

function label(value: string) {
  return value.replaceAll("_", " ");
}

export function ProposalExecution({ noticeId }: { noticeId: string }) {
  const [data, setData] = useState<Payload | null>(null);
  const [busy, setBusy] = useState("");
  const [message, setMessage] = useState("");
  const [findingTitle, setFindingTitle] = useState("");
  const [findingSeverity, setFindingSeverity] = useState("medium");

  const base = `/ai/opportunities/${encodeURIComponent(noticeId)}`;

  const load = useCallback(async () => {
    const result = await apiGet<Payload>(`${base}/proposal-execution/`);
    setData(result);
  }, [base]);

  useEffect(() => {
    let cancelled = false;
    apiGet<Payload>(`${base}/proposal-execution/`)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((error: unknown) => {
        if (!cancelled) setMessage(error instanceof Error ? error.message : "Proposal execution could not be loaded.");
      });
    return () => {
      cancelled = true;
    };
  }, [base]);

  async function updateRequirement(id: number, patch: Record<string, unknown>) {
    setBusy(`req-${id}`);
    try {
      setData(await apiPatch<Payload>(`${base}/proposal-requirements/${id}/`, patch));
      setMessage("Requirement updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Requirement could not be updated.");
    } finally {
      setBusy("");
    }
  }

  async function updateReview(id: number, patch: Record<string, unknown>) {
    setBusy(`review-${id}`);
    try {
      setData(await apiPatch<Payload>(`${base}/proposal-reviews/${id}/`, patch));
      setMessage("Review gate updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Review gate could not be updated.");
    } finally {
      setBusy("");
    }
  }

  async function updateFinding(id: number, patch: Record<string, unknown>) {
    setBusy(`finding-${id}`);
    try {
      setData(await apiPatch<Payload>(`${base}/proposal-findings/${id}/`, patch));
      setMessage("Finding updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Finding could not be updated.");
    } finally {
      setBusy("");
    }
  }

  async function updatePlan(patch: Record<string, unknown>) {
    setBusy("plan");
    try {
      setData(await apiPost<Payload>(`${base}/proposal-execution/`, { action: "update_plan", ...patch }));
      setMessage("Proposal plan updated.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proposal plan could not be updated.");
    } finally {
      setBusy("");
    }
  }

  async function acceptAmendmentBaseline() {
    setBusy("amendment");
    try {
      setData(await apiPost<Payload>(`${base}/proposal-execution/`, { action: "accept_amendment_baseline" }));
      setMessage("Current solicitation state accepted as the new amendment baseline.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Amendment baseline could not be updated.");
    } finally {
      setBusy("");
    }
  }

  async function createFinding() {
    if (!findingTitle.trim()) return;
    setBusy("new-finding");
    try {
      setData(
        await apiPost<Payload>(`${base}/proposal-execution/`, {
          action: "create_finding",
          title: findingTitle.trim(),
          severity: findingSeverity,
        }),
      );
      setFindingTitle("");
      setMessage("Review finding created.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Finding could not be created.");
    } finally {
      setBusy("");
    }
  }

  const readinessLabel = useMemo(() => {
    if (!data) return "";
    if (data.plan.submission_ready) return "Submission ready";
    if (data.counts.critical_open_findings) return "Blocked by critical finding";
    if (data.amendment_impact.changed) return "Amendment review required";
    return "Work in progress";
  }, [data]);

  if (!data) {
    return (
      <section className="data-panel proposal-loading">
        <LoaderCircle className="spin" />
        <strong>Loading proposal execution</strong>
        {message && <p>{message}</p>}
      </section>
    );
  }

  return (
    <section className="proposal-execution-shell">
      <header className="proposal-command-header">
        <div>
          <span className="eyebrow">PROPOSAL EXECUTION + REVIEW MANAGEMENT</span>
          <h2>Move the response from requirements to submission</h2>
          <p>Owners, review gates, findings, amendment impact, Project Room work, and final submission readiness stay tied to this opportunity.</p>
        </div>
        <button className="secondary-button" onClick={() => void load()} disabled={Boolean(busy)}>
          <RefreshCw size={16} /> Refresh
        </button>
      </header>

      {message && <p className="inline-message">{message}</p>}

      {data.amendment_impact.changed && (
        <div className="proposal-amendment-alert">
          <AlertTriangle size={20} />
          <div>
            <strong>Solicitation change detected</strong>
            {data.amendment_impact.changes.map((row, index) => <p key={index}>{row}</p>)}
          </div>
          <button className="secondary-button" onClick={() => void acceptAmendmentBaseline()} disabled={busy === "amendment"}>
            Mark reviewed
          </button>
        </div>
      )}

      <div className="proposal-kpis proposal-execution-kpis">
        <article>
          <span>Submission readiness</span>
          <strong>{data.plan.readiness_score}%</strong>
          <small>{readinessLabel}</small>
        </article>
        <article>
          <span>Requirements</span>
          <strong>{data.counts.requirements_closed}/{data.counts.requirements_total}</strong>
          <small>human-verified closed</small>
        </article>
        <article>
          <span>Reviews passed</span>
          <strong>{data.counts.reviews_passed}/{data.counts.reviews_total}</strong>
          <small>Pink / Red / Gold / final</small>
        </article>
        <article>
          <span>Open findings</span>
          <strong>{data.counts.open_findings}</strong>
          <small>{data.counts.critical_open_findings} critical</small>
        </article>
      </div>

      <div className="proposal-execution-grid">
        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">COMPLIANCE EXECUTION</span><h3>Requirement ownership</h3></div>
            <ClipboardCheck />
          </div>
          <div className="proposal-execution-requirements">
            {data.requirements.map((row) => (
              <article key={row.id}>
                <div className="proposal-execution-requirement-main">
                  <span className={`proposal-state ${row.status}`}>{label(row.status)}</span>
                  <strong>{row.requirement}</strong>
                  <p>{row.evidence}</p>
                  <small>{row.source} · {row.open_findings} open findings</small>
                </div>
                <div className="proposal-execution-controls">
                  <select value={row.status} onChange={(event) => void updateRequirement(row.id, { status: event.target.value })} disabled={busy === `req-${row.id}`}>
                    {requirementStatuses.map((status) => <option key={status} value={status}>{label(status)}</option>)}
                  </select>
                  <select value={row.owner_id ?? ""} onChange={(event) => void updateRequirement(row.id, { owner_id: event.target.value ? Number(event.target.value) : null })}>
                    <option value="">Unassigned</option>
                    {data.members.map((member) => <option key={member.user_id} value={member.user_id}>{member.name}</option>)}
                  </select>
                </div>
              </article>
            ))}
          </div>
        </section>

        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">COLOR REVIEW GATES</span><h3>Review control</h3></div>
            <ShieldCheck />
          </div>
          <div className="proposal-review-gates">
            {data.reviews.map((row) => (
              <article key={row.id} className={`review-${row.status}`}>
                <div>
                  <strong>{row.label}</strong>
                  <p>{row.target_at ? new Date(row.target_at).toLocaleString() : "No target date"}</p>
                  <small>{row.open_findings} open findings · {row.owner || "Unassigned"}</small>
                </div>
                <select value={row.status} onChange={(event) => void updateReview(row.id, { status: event.target.value })}>
                  {reviewStatuses.map((status) => <option key={status} value={status}>{label(status)}</option>)}
                </select>
              </article>
            ))}
          </div>
        </section>
      </div>

      <div className="proposal-execution-grid">
        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">REVIEW FINDINGS</span><h3>Issues that must be dispositioned</h3></div>
            <Flag />
          </div>
          <div className="proposal-new-finding">
            <input value={findingTitle} onChange={(event) => setFindingTitle(event.target.value)} placeholder="Add a review finding" />
            <select value={findingSeverity} onChange={(event) => setFindingSeverity(event.target.value)}>
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
              <option value="critical">Critical</option>
            </select>
            <button className="primary-button" onClick={() => void createFinding()} disabled={!findingTitle.trim() || busy === "new-finding"}>Add finding</button>
          </div>
          <div className="proposal-findings">
            {data.findings.map((row) => (
              <article key={row.id} className={`finding-${row.severity}`}>
                <div><span>{row.severity}</span><strong>{row.title}</strong><p>{row.detail || "No detail added."}</p></div>
                <select value={row.status} onChange={(event) => void updateFinding(row.id, { status: event.target.value })}>
                  <option value="open">Open</option>
                  <option value="resolved">Resolved</option>
                  <option value="accepted">Accepted risk</option>
                </select>
              </article>
            ))}
            {!data.findings.length && <p>No review findings have been recorded.</p>}
          </div>
        </section>

        <section className="data-panel">
          <div className="panel-title-row">
            <div><span className="eyebrow">TEAM EXECUTION</span><h3>Project Room proposal work</h3></div>
            <Users />
          </div>
          <div className="proposal-project-tasks">
            {data.project_room_tasks.map((task) => (
              <article key={task.id}>
                <strong>{task.title}</strong>
                <p>{task.assigned_to || "Unassigned"} · {label(task.status)}</p>
                <small>{task.due_date || "No due date"} · {task.priority} priority</small>
              </article>
            ))}
            {!data.project_room_tasks.length && <p>Create or link a Project Room to coordinate proposal work with the team.</p>}
          </div>
        </section>
      </div>

      <section className="data-panel proposal-submission-control">
        <div className="panel-title-row">
          <div><span className="eyebrow">FINAL SUBMISSION CONTROL</span><h3>Human-controlled submission gate</h3></div>
          {data.plan.submission_ready ? <CheckCircle2 /> : <AlertTriangle />}
        </div>
        <label>
          Submission method / portal
          <input
            defaultValue={data.plan.submission_method}
            onBlur={(event) => void updatePlan({ submission_method: event.target.value })}
            placeholder="SAM.gov, PIEE, email, agency portal..."
          />
        </label>
        <label className="proposal-verification-check">
          <input
            type="checkbox"
            checked={data.plan.final_submission_verified}
            onChange={(event) => void updatePlan({ final_submission_verified: event.target.checked })}
          />
          <span>I verified the current solicitation, amendments, required volumes, file naming, delivery method, and submission instructions.</span>
        </label>
        <div className={`proposal-final-state ${data.plan.submission_ready ? "ready" : "blocked"}`}>
          <strong>{data.plan.submission_ready ? "Submission Ready" : "Not Submission Ready"}</strong>
          <p>{data.plan.submission_ready ? "All tracked execution gates are satisfied." : "Resolve remaining requirements, reviews, findings, amendment impact, and final verification before submission."}</p>
        </div>
      </section>

      <p className="proposal-warning">{data.warning}</p>
    </section>
  );
}
