"use client";
import { useEffect, useState } from "react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";
type Log={id:number;action:string;object_type:string;object_id:string;actor_name:string;created_at:string};
export default function AuditLogPage(){const {session}=useAuth();const [rows,setRows]=useState<Log[]>([]);const [message,setMessage]=useState("");const admin=["owner","admin"].includes(session?.role||"");useEffect(()=>{if(admin)authFetch<Log[]>("/audit-logs/").then(setRows).catch(e=>setMessage(e.message));},[admin]);return <><header className="feature-hero"><div><span className="eyebrow">Security</span><h1>Audit log</h1><p>Review important account, team, and workspace activity.</p></div></header><section className="data-panel">{!admin?<p>Only owners and administrators can view audit logs.</p>:message?<p>{message}</p>:<div className="simple-table">{rows.map(row=><div className="simple-row" key={row.id}><span><b>{row.action}</b><small>{row.actor_name} · {row.object_type} {row.object_id}</small></span><time>{new Date(row.created_at).toLocaleString()}</time></div>)}</div>}</section></>;}
