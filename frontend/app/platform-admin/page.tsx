"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Building2, Flag, Gauge, LockKeyhole, RefreshCw,
  ShieldCheck, Users, Wrench, ClipboardList
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Dashboard = {
  organizations: { total: number; active: number; pending: number; suspended: number };
  users: { total: number; active: number; suspended: number };
  beta_pending: number;
  feature_flags: number;
  platform_mode: "normal" | "maintenance";
  recent_events: Array<{ id:number; action:string; target_type:string; target_id:string; reason:string; created_at:string }>;
};
type Org = { id:number; name:string; status:string; beta_access:boolean; member_count:number; suspension_reason:string; beta_status?:string|null };
type UserRow = { id:number; email:string; first_name:string; last_name:string; platform_status:string; platform_role?:string|null; mfa_verified:boolean; last_login?:string|null };
type FlagRow = { id:number; key:string; name:string; description:string; enabled:boolean; updated_at:string };
type Beta = { id:number; organization_id:number; organization_name:string; status:string; applicant_email:string; application_notes:string; requested_information:string; submitted_at:string };
type Audit = { id:number; action:string; actor_email:string; target_type:string; target_id:string; reason:string; created_at:string };
type IntegrityQuarantine = { id:number; source:string; record_type:string; source_id:string; reason:string; error_message:string; occurrences:number };
type System = {
  connectors?: unknown; connector_registry?: unknown; connector_error?: string;
  operations?: { data_integrity?: { summary?: { version_rows:number; tracked_records:number; unresolved_quarantine:number }; quarantine?: IntegrityQuarantine[] } };
};

const tabs = [
  ["dashboard","Command Dashboard", Gauge],
  ["organizations","Organizations", Building2],
  ["users","Users", Users],
  ["beta","Private Beta", LockKeyhole],
  ["security","Security Operations", ShieldCheck],
  ["features","Feature Controls", Flag],
  ["system","System Operations", Activity],
] as const;

export default function PlatformAdminPage() {
  const [tab,setTab]=useState<(typeof tabs)[number][0]>("dashboard");
  const [role,setRole]=useState("");
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [dash,setDash]=useState<Dashboard|null>(null);
  const [orgs,setOrgs]=useState<Org[]>([]);
  const [users,setUsers]=useState<UserRow[]>([]);
  const [flags,setFlags]=useState<FlagRow[]>([]);
  const [beta,setBeta]=useState<Beta[]>([]);
  const [audit,setAudit]=useState<Audit[]>([]);
  const [system,setSystem]=useState<System>({});
  const [q,setQ]=useState("");

  const superAdmin = role === "super_admin";

  const load = useCallback(async () => {
    setBusy(true); setError("");
    try {
      const me = await apiGet<{platform_admin:boolean; role:string}>("/platform-admin/me/");
      setRole(me.role);
      const [d,o,u,b,f,a,s] = await Promise.all([
        apiGet<Dashboard>("/platform-admin/dashboard/"),
        apiGet<{results:Org[]}>("/platform-admin/organizations/"),
        apiGet<{results:UserRow[]}>("/platform-admin/users/"),
        apiGet<{results:Beta[]}>("/platform-admin/beta/"),
        apiGet<{results:FlagRow[]}>("/platform-admin/feature-flags/"),
        apiGet<{results:Audit[]}>("/platform-admin/audit/"),
        apiGet<System>("/platform-admin/system/"),
      ]);
      setDash(d); setOrgs(o.results); setUsers(u.results); setBeta(b.results);
      setFlags(f.results); setAudit(a.results); setSystem(s);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Platform administration could not be loaded.");
    } finally { setBusy(false); }
  }, []);

  useEffect(() => {
    let cancelled=false;
    Promise.resolve().then(()=>{ if(!cancelled) void load(); });
    return ()=>{cancelled=true};
  }, [load]);

  const filteredOrgs=useMemo(()=>orgs.filter(x=>x.name.toLowerCase().includes(q.toLowerCase())),[orgs,q]);
  const filteredUsers=useMemo(()=>users.filter(x=>`${x.email} ${x.first_name} ${x.last_name}`.toLowerCase().includes(q.toLowerCase())),[users,q]);

  async function orgAction(id:number, action:string) {
    if(!superAdmin) return;
    const reason = action==="suspend" ? window.prompt("Suspension reason") ?? "" : "";
    await apiPost(`/platform-admin/organizations/${id}/action/`, {action,reason});
    await load();
  }
  async function userAction(id:number, action:string) {
    if(!superAdmin) return;
    const reason = action==="suspend" || action==="disable" ? window.prompt("Reason") ?? "" : "";
    await apiPost(`/platform-admin/users/${id}/action/`, {action,reason});
    await load();
  }
  async function betaAction(id:number, action:string) {
    if(!superAdmin) return;
    const requested_information = action==="request_info" ? window.prompt("What information is required?") ?? "" : "";
    await apiPost(`/platform-admin/beta/${id}/action/`, {action,requested_information});
    await load();
  }
  async function toggleFlag(flag:FlagRow) {
    if(!superAdmin) return;
    await apiPost("/platform-admin/feature-flags/", {key:flag.key,enabled:!flag.enabled});
    await load();
  }
  async function retryQuarantine(id:number) {
    if(!superAdmin) return;
    await apiPost(`/platform-admin/data-integrity/quarantine/${id}/retry/`, {});
    await load();
  }
  async function setMode(mode:"normal"|"maintenance") {
    if(!superAdmin) return;
    if(mode==="maintenance" && !window.confirm("Enable maintenance mode for normal ForgeGov users?")) return;
    await apiPost("/platform-admin/platform-state/", {mode});
    await load();
  }

  if(error) return <div className="platform-admin-shell"><section className="platform-admin-denied"><ShieldCheck/><h1>Platform Administration</h1><p>{error}</p></section></div>;
  if(!dash) return <div className="platform-admin-shell"><section className="platform-admin-denied"><RefreshCw className="spin"/><h1>Loading platform control plane…</h1></section></div>;

  return <div className="platform-admin-shell">
    <header className="platform-admin-hero">
      <div><span className="eyebrow">FORGEGOV CONTROL PLANE</span><h1>Platform Administration</h1><p>Private beta, security, organization, user, feature, and system operations.</p></div>
      <div className="platform-admin-role"><ShieldCheck size={17}/>{role.replaceAll("_"," ")}</div>
    </header>

    <nav className="platform-admin-tabs">
      {tabs.map(([key,label,Icon])=><button key={key} className={tab===key?"active":""} onClick={()=>setTab(key)}><Icon size={16}/>{label}</button>)}
    </nav>

    {busy && <div className="platform-admin-loading">Refreshing platform state…</div>}

    {tab==="dashboard" && <main className="platform-admin-stack">
      <section className="platform-admin-metrics">
        <div><Building2/><span>Organizations</span><strong>{dash.organizations.total}</strong><small>{dash.organizations.active} active · {dash.organizations.pending} pending</small></div>
        <div><Users/><span>Users</span><strong>{dash.users.total}</strong><small>{dash.users.active} active · {dash.users.suspended} suspended</small></div>
        <div><LockKeyhole/><span>Beta queue</span><strong>{dash.beta_pending}</strong><small>Pending review</small></div>
        <div><Flag/><span>Feature controls</span><strong>{dash.feature_flags}</strong><small>{dash.platform_mode} mode</small></div>
      </section>
      <section className="platform-admin-panel"><header><h2>Platform state</h2></header><div className="platform-admin-actions">
        <button disabled={!superAdmin || dash.platform_mode==="normal"} onClick={()=>void setMode("normal")}>Normal operation</button>
        <button disabled={!superAdmin || dash.platform_mode==="maintenance"} onClick={()=>void setMode("maintenance")}>Maintenance mode</button>
      </div></section>
      <section className="platform-admin-panel"><header><h2>Recent administrative activity</h2></header>
        <div className="platform-admin-table">{dash.recent_events.map(e=><div className="platform-admin-row" key={e.id}><b>{e.action}</b><span>{e.target_type} {e.target_id}</span><small>{new Date(e.created_at).toLocaleString()}</small></div>)}</div>
      </section>
    </main>}

    {tab==="organizations" && <main className="platform-admin-stack">
      <section className="platform-admin-toolbar"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search organizations"/></section>
      <section className="platform-admin-panel"><div className="platform-admin-table">{filteredOrgs.map(o=><div className="platform-admin-record" key={o.id}>
        <div><b>{o.name}</b><span>{o.member_count} members · beta {o.beta_access?"enabled":"disabled"}</span></div>
        <em className={`state-${o.status}`}>{o.status}</em>
        <div className="platform-admin-actions">{superAdmin&&<>
          {o.status==="pending"&&<button onClick={()=>void orgAction(o.id,"approve")}>Approve</button>}
          {o.status!=="active"&&o.status!=="suspended"&&<button onClick={()=>void orgAction(o.id,"activate")}>Activate</button>}
          {o.status==="active"&&<button onClick={()=>void orgAction(o.id,"suspend")}>Suspend</button>}
          {o.status==="suspended"&&<button onClick={()=>void orgAction(o.id,"reactivate")}>Reactivate</button>}
          <button onClick={()=>void orgAction(o.id,"disable")}>Disable</button>
        </>}</div>
      </div>)}</div></section>
    </main>}

    {tab==="users" && <main className="platform-admin-stack">
      <section className="platform-admin-toolbar"><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search users"/></section>
      <section className="platform-admin-panel"><div className="platform-admin-table">{filteredUsers.map(u=><div className="platform-admin-record" key={u.id}>
        <div><b>{u.first_name||u.last_name?`${u.first_name} ${u.last_name}`:u.email}</b><span>{u.email} · {u.platform_role||"tenant user"} {u.platform_role?`· MFA ${u.mfa_verified?"verified":"required"}`:""}</span></div>
        <em className={`state-${u.platform_status}`}>{u.platform_status}</em>
        <div className="platform-admin-actions">{superAdmin&&<>
          {u.platform_status==="active"?<button onClick={()=>void userAction(u.id,"suspend")}>Suspend</button>:<button onClick={()=>void userAction(u.id,"reactivate")}>Reactivate</button>}
          <button onClick={()=>void userAction(u.id,"disable")}>Disable</button>
        </>}</div>
      </div>)}</div></section>
    </main>}

    {tab==="beta" && <main className="platform-admin-stack"><section className="platform-admin-panel"><div className="platform-admin-table">{beta.map(b=><div className="platform-admin-record" key={b.id}>
      <div><b>{b.organization_name}</b><span>{b.applicant_email||"No applicant email"} · submitted {new Date(b.submitted_at).toLocaleDateString()}</span></div>
      <em className={`state-${b.status}`}>{b.status.replaceAll("_"," ")}</em>
      <div className="platform-admin-actions">{superAdmin&&<>
        <button onClick={()=>void betaAction(b.id,"approve")}>Approve</button>
        <button onClick={()=>void betaAction(b.id,"request_info")}>Request info</button>
        <button onClick={()=>void betaAction(b.id,"reject")}>Reject</button>
      </>}</div>
    </div>)}</div></section></main>}

    {tab==="security" && <main className="platform-admin-stack">
      <section className="platform-admin-panel"><header><h2>Administrative audit</h2><p>Platform-level privileged state changes. Tenant audit remains separate.</p></header>
      <div className="platform-admin-table">{audit.map(a=><div className="platform-admin-row" key={a.id}><b>{a.action}</b><span>{a.actor_email||"system"} · {a.target_type} {a.target_id}</span><small>{new Date(a.created_at).toLocaleString()}</small></div>)}</div></section>
    </main>}

    {tab==="features" && <main className="platform-admin-stack"><section className="platform-admin-panel"><div className="platform-admin-table">{flags.map(f=><div className="platform-admin-record" key={f.id}>
      <div><b>{f.name}</b><span>{f.key}{f.description?` · ${f.description}`:""}</span></div>
      <em className={f.enabled?"state-active":"state-disabled"}>{f.enabled?"enabled":"disabled"}</em>
      <div className="platform-admin-actions"><button disabled={!superAdmin} onClick={()=>void toggleFlag(f)}>{f.enabled?"Disable":"Enable"}</button></div>
    </div>)}</div></section></main>}

    {tab==="system" && <main className="platform-admin-stack">
      <section className="platform-admin-panel"><header><h2>Connector & system health</h2><p>Live readiness, connector health, sync freshness, source history, and quarantine state.</p></header>
        {system.operations?.data_integrity?.summary && <div className="platform-admin-metrics">
          <div><ClipboardList/><span>Tracked records</span><strong>{system.operations.data_integrity.summary.tracked_records}</strong><small>{system.operations.data_integrity.summary.version_rows} source versions</small></div>
          <div><Wrench/><span>Quarantine</span><strong>{system.operations.data_integrity.summary.unresolved_quarantine}</strong><small>Unresolved source records</small></div>
        </div>}
        {(system.operations?.data_integrity?.quarantine?.length ?? 0) > 0 && <div className="platform-admin-table">
          {system.operations?.data_integrity?.quarantine?.map(row=><div className="platform-admin-record" key={row.id}>
            <div><b>{row.source} · {row.record_type}</b><span>{row.source_id || "No source ID"} · {row.reason} · seen {row.occurrences}x</span></div>
            <em className="state-suspended">quarantined</em>
            <div className="platform-admin-actions"><button disabled={!superAdmin} onClick={()=>void retryQuarantine(row.id)}>Retry</button></div>
          </div>)}
        </div>}
        <pre className="platform-admin-json">{JSON.stringify(system,null,2)}</pre>
      </section>
    </main>}
  </div>;
}
