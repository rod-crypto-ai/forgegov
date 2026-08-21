"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, Check, CheckCheck, Mail, RefreshCw, Settings2, X } from "lucide-react";
import { apiGet, apiPatch, authFetch, normalizeList } from "@/lib/api";

type Notification={id:number;title:string;message:string;kind:string;read:boolean;link:string;created_at:string};
type IntelligenceAlert={id:number;title:string;summary:string;alert_type:string;read:boolean;internal_link:string;created_at:string};
type EmployeeInvite={id:number;email:string;organization_name:string;invited_by_name:string;role:string;job_title:string;department:string;status:string;expires_at:string};
type Preference={
  in_app_enabled:boolean;email_enabled:boolean;immediate_critical:boolean;daily_digest:boolean;weekly_digest:boolean;
  opportunity_alerts:boolean;opportunity_changes:boolean;deadlines:boolean;pipeline:boolean;project_room:boolean;security:boolean;
};
type Delivery={id:number;category:string;subject:string;status:string;error_message:string;sent_at?:string|null;created_at:string};

const preferenceLabels: Array<[keyof Preference,string]> = [
  ["in_app_enabled","In-app notifications"],
  ["email_enabled","Email delivery"],
  ["immediate_critical","Immediate critical alerts"],
  ["daily_digest","Daily Intelligence Brief"],
  ["weekly_digest","Weekly Intelligence Brief"],
  ["opportunity_alerts","New opportunity matches"],
  ["opportunity_changes","Opportunity changes & amendments"],
  ["deadlines","Deadlines"],
  ["pipeline","Pipeline activity"],
  ["project_room","Project Room activity"],
  ["security","Security activity"],
];

export default function NotificationsPage(){
 const [rows,setRows]=useState<Notification[]>([]);
 const [alerts,setAlerts]=useState<IntelligenceAlert[]>([]);
 const [invites,setInvites]=useState<EmployeeInvite[]>([]);
 const [preference,setPreference]=useState<Preference|null>(null);
 const [deliveries,setDeliveries]=useState<Delivery[]>([]);
 const [message,setMessage]=useState("");
 const [busy,setBusy]=useState("");
 const [filter,setFilter]=useState("all");
 const load=useCallback(async()=>{try{const [notificationData,alertData,inviteData,prefData,deliveryData]=await Promise.all([
   apiGet<Notification[]>("/collaboration/notifications/?page_size=250"),
   apiGet<IntelligenceAlert[]>("/alerts/?dismissed=false&page_size=250"),
   authFetch<EmployeeInvite[]>("/auth/invitations/pending/"),
   apiGet<Preference>("/notifications/preferences/"),
   apiGet<{results:Delivery[]}>("/notifications/deliveries/"),
 ]);setRows(normalizeList(notificationData));setAlerts(normalizeList(alertData));setInvites(normalizeList(inviteData));setPreference(prefData);setDeliveries(deliveryData.results??[]);setMessage("")}catch(e){setMessage(e instanceof Error?e.message:"Notifications could not be loaded")}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function markNotification(id:number,read=true){await apiPatch(`/collaboration/notifications/${id}/`,{read});await load()}
 async function markAlert(id:number,read=true){await apiPatch(`/alerts/${id}/`,{read});await load()}
 async function markAll(){await Promise.all([
   ...rows.filter(r=>!r.read).map(r=>apiPatch(`/collaboration/notifications/${r.id}/`,{read:true})),
   ...alerts.filter(r=>!r.read).map(r=>apiPatch(`/alerts/${r.id}/`,{read:true})),
 ]);await load()}
 async function respond(id:number,action:"accept"|"decline"){setBusy(`${action}-${id}`);try{await authFetch(`/auth/invitations/${id}/respond/`,{method:"POST",body:JSON.stringify({action})});setMessage(action==="accept"?"Company invitation accepted.":"Company invitation declined.");await load()}catch(e){setMessage(e instanceof Error?e.message:"Invitation response failed")}finally{setBusy("")}}
 async function togglePreference(key:keyof Preference){if(!preference)return;const next={...preference,[key]:!preference[key]};setPreference(next);try{await apiPatch("/notifications/preferences/",{[key]:next[key]});setMessage("Notification preference saved.")}catch(e){setPreference(preference);setMessage(e instanceof Error?e.message:"Preference could not be saved")}}
 const unread=useMemo(()=>rows.filter(row=>!row.read).length+alerts.filter(row=>!row.read).length,[rows,alerts]);
 const visibleRows=useMemo(()=>rows.filter(row=>filter==="all"||row.kind.includes(filter)),[rows,filter]);
 const visibleAlerts=useMemo(()=>alerts.filter(row=>filter==="all"||row.alert_type.includes(filter)),[alerts,filter]);
 return <div className="page-stack notifications-page"><header className="module-header"><div><span className="eyebrow">NOTIFICATION CENTER</span><h1>Intelligence, deadlines, invitations, and team activity</h1><p>ForgeGov combines opportunity intelligence with capture and collaboration events so your team can act from one inbox.</p></div><div className="row-actions"><button className="secondary-button" onClick={()=>void load()}><RefreshCw size={16}/> Refresh</button><button className="primary-button" disabled={!unread} onClick={()=>void markAll()}><CheckCheck size={16}/> Mark all read</button></div></header>{message&&<div className="system-banner warning">{message}</div>}
 {invites.length>0&&<section className="data-panel invitation-inbox"><div className="panel-heading"><Bell/><div><h2>Company invitations</h2><p>Accept only invitations from companies you recognize. Existing members of another company should use partner collaboration instead.</p></div></div>{invites.map(invite=><article key={invite.id}><div><span className="eyebrow">EMPLOYEE INVITATION</span><h3>{invite.organization_name}</h3><p>{invite.invited_by_name} invited you as {invite.job_title||invite.role}{invite.department?` in ${invite.department}`:""}.</p><small>Expires {new Date(invite.expires_at).toLocaleString()}</small></div><div className="row-actions"><button className="primary-button" disabled={busy!==""} onClick={()=>void respond(invite.id,"accept")}><Check size={16}/> Accept</button><button className="secondary-button" disabled={busy!==""} onClick={()=>void respond(invite.id,"decline")}><X size={16}/> Decline</button></div></article>)}</section>}
 <section className="data-panel notification-preferences"><div className="panel-heading"><Settings2/><div><h2>Delivery preferences</h2><p>Choose which ForgeGov events reach you and whether you receive daily or weekly intelligence email briefs.</p></div></div>{preference&&<div className="notification-preference-grid">{preferenceLabels.map(([key,label])=><label key={key}><input type="checkbox" checked={Boolean(preference[key])} onChange={()=>void togglePreference(key)}/><span>{label}</span></label>)}</div>}</section>
 <section className="data-panel"><div className="panel-heading"><Bell/><div><h2>Unified inbox</h2><p>{unread} unread intelligence and collaboration update{unread===1?"":"s"}.</p></div><select value={filter} onChange={e=>setFilter(e.target.value)}><option value="all">All categories</option><option value="opportunity">Opportunities</option><option value="deadline">Deadlines</option><option value="pipeline">Pipeline</option><option value="project_room">Project Rooms</option><option value="security">Security</option></select></div><div className="notification-center-list">{!visibleRows.length&&!visibleAlerts.length?<div className="table-state"><Bell/><strong>No notifications in this category</strong><p>New matches, source changes, deadlines, and team activity will appear here.</p></div>:<>
 {visibleAlerts.map(row=><article className={row.read?"notification-read":""} key={`a-${row.id}`}><Bell size={18}/><div><span>{row.alert_type.replaceAll("_"," ")}</span><h3>{row.title}</h3><p>{row.summary}</p><small>{new Date(row.created_at).toLocaleString()}</small></div><div className="row-actions"><Link className="primary-button" href={row.internal_link||"/capture/alerts"}>Open</Link><button className="secondary-button" onClick={()=>void markAlert(row.id,!row.read)}>{row.read?"Mark unread":"Mark read"}</button></div></article>)}
 {visibleRows.map(row=><article className={row.read?"notification-read":""} key={`n-${row.id}`}><Bell size={18}/><div><span>{row.kind.replaceAll("_"," ")}</span><h3>{row.title}</h3><p>{row.message}</p><small>{new Date(row.created_at).toLocaleString()}</small></div><div className="row-actions">{row.link&&<Link className="primary-button" href={row.link}>Open</Link>}<button className="secondary-button" onClick={()=>void markNotification(row.id,!row.read)}>{row.read?"Mark unread":"Mark read"}</button></div></article>)}
 </>}</div></section>
 <section className="data-panel"><div className="panel-heading"><Mail/><div><h2>Email delivery history</h2><p>Recent ForgeGov intelligence briefs and critical-alert delivery status.</p></div></div><div className="notification-delivery-list">{!deliveries.length?<div className="table-state"><Mail/><strong>No email deliveries yet</strong><p>Your daily/weekly briefs and critical alert deliveries will be recorded here.</p></div>:deliveries.slice(0,20).map(row=><article key={row.id}><div><strong>{row.subject}</strong><span>{row.category.replaceAll("_"," ")}</span></div><em className={`state-${row.status}`}>{row.status}</em><small>{new Date(row.sent_at||row.created_at).toLocaleString()}</small>{row.error_message&&<p>{row.error_message}</p>}</article>)}</div></section>
 </div>
}
