"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, Check, CheckCheck, RefreshCw, X } from "lucide-react";
import { apiGet, apiPatch, authFetch, normalizeList } from "@/lib/api";

type Notification={id:number;title:string;message:string;kind:string;read:boolean;link:string;created_at:string};
type EmployeeInvite={id:number;email:string;organization_name:string;invited_by_name:string;role:string;job_title:string;department:string;status:string;expires_at:string};

export default function NotificationsPage(){
 const [rows,setRows]=useState<Notification[]>([]);
 const [invites,setInvites]=useState<EmployeeInvite[]>([]);
 const [message,setMessage]=useState("");
 const [busy,setBusy]=useState("");
 const load=useCallback(async()=>{try{const [notificationData,inviteData]=await Promise.all([apiGet<Notification[]>("/collaboration/notifications/?page_size=250"),authFetch<EmployeeInvite[]>("/auth/invitations/pending/")]);setRows(normalizeList(notificationData));setInvites(normalizeList(inviteData));setMessage("")}catch(e){setMessage(e instanceof Error?e.message:"Notifications could not be loaded")}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function mark(id:number,read=true){await apiPatch(`/collaboration/notifications/${id}/`,{read});await load()}
 async function markAll(){await Promise.all(rows.filter(r=>!r.read).map(r=>apiPatch(`/collaboration/notifications/${r.id}/`,{read:true})));await load()}
 async function respond(id:number,action:"accept"|"decline"){setBusy(`${action}-${id}`);try{await authFetch(`/auth/invitations/${id}/respond/`,{method:"POST",body:JSON.stringify({action})});setMessage(action==="accept"?"Company invitation accepted.":"Company invitation declined.");await load()}catch(e){setMessage(e instanceof Error?e.message:"Invitation response failed")}finally{setBusy("")}}
 const unread=useMemo(()=>rows.filter(row=>!row.read).length,[rows]);
 return <div className="page-stack notifications-page"><header className="module-header"><div><span className="eyebrow">NOTIFICATION CENTER</span><h1>Invitations, access changes, and collaboration updates</h1><p>Employee invitations addressed to your email appear here even before you join the inviting company.</p></div><div className="row-actions"><button className="secondary-button" onClick={()=>void load()}><RefreshCw size={16}/> Refresh</button><button className="primary-button" disabled={!unread} onClick={()=>void markAll()}><CheckCheck size={16}/> Mark all read</button></div></header>{message&&<div className="system-banner warning">{message}</div>}
 {invites.length>0&&<section className="data-panel invitation-inbox"><div className="panel-heading"><Bell/><div><h2>Company invitations</h2><p>Accept only invitations from companies you recognize. Existing members of another company should use partner collaboration instead.</p></div></div>{invites.map(invite=><article key={invite.id}><div><span className="eyebrow">EMPLOYEE INVITATION</span><h3>{invite.organization_name}</h3><p>{invite.invited_by_name} invited you as {invite.job_title||invite.role}{invite.department?` in ${invite.department}`:""}.</p><small>Expires {new Date(invite.expires_at).toLocaleString()}</small></div><div className="row-actions"><button className="primary-button" disabled={busy!==""} onClick={()=>void respond(invite.id,"accept")}><Check size={16}/> Accept</button><button className="secondary-button" disabled={busy!==""} onClick={()=>void respond(invite.id,"decline")}><X size={16}/> Decline</button></div></article>)}</section>}
 <section className="data-panel notification-center-list">{!rows.length?<div className="table-state"><Bell/><strong>No collaboration notifications yet</strong><p>Partner invitations, connection requests, assignments, and Project Room activity will appear here.</p></div>:rows.map(row=><article className={row.read?"notification-read":""} key={row.id}><Bell size={18}/><div><span>{row.kind.replaceAll("_"," ")}</span><h3>{row.title}</h3><p>{row.message}</p><small>{new Date(row.created_at).toLocaleString()}</small></div><div className="row-actions">{row.link&&<Link className="primary-button" href={row.link}>Open</Link>}<button className="secondary-button" onClick={()=>void mark(row.id,!row.read)}>{row.read?"Mark unread":"Mark read"}</button></div></article>)}</section></div>
}
