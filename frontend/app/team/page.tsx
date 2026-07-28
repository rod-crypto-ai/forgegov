"use client";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { UserPlus } from "lucide-react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

type Member={id:number;role:string;user:{email:string;first_name:string;last_name:string}};
type Invite={id:number;email:string;role:string;status:string;expires_at:string;invite_url?:string};
export default function TeamPage(){
 const {session}=useAuth(); const [members,setMembers]=useState<Member[]>([]); const [invites,setInvites]=useState<Invite[]>([]); const [email,setEmail]=useState(""); const [role,setRole]=useState("viewer"); const [message,setMessage]=useState("");
 const admin=["owner","admin"].includes(session?.role||"");
 const load=useCallback(async()=>{if(!admin)return;try{setMembers(await authFetch("/team/members/"));setInvites(await authFetch("/team/invitations/"));}catch(error){setMessage(error instanceof Error?error.message:"Could not load team");}},[admin]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer);},[load]);
 async function invite(e:FormEvent){e.preventDefault();try{const row=await authFetch<Invite>("/team/invitations/",{method:"POST",body:JSON.stringify({email,role})});setMessage(`Invitation created. Copy this link: ${row.invite_url}`);setEmail("");await load();}catch(error){setMessage(error instanceof Error?error.message:"Invite failed");}}
 return <><header className="feature-hero"><div><span className="eyebrow">Workspace administration</span><h1>Team and permissions</h1><p>Invite users and control access to your organization’s ForgeGov data.</p></div></header>{!admin?<section className="data-panel"><p>Only workspace owners and administrators can manage team access.</p></section>:<><section className="data-panel"><h2>Invite a team member</h2><form className="advanced-filter-grid" onSubmit={invite}><label><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required/></label><label><span>Role</span><select value={role} onChange={e=>setRole(e.target.value)}><option value="admin">Administrator</option><option value="capture">Capture Manager</option><option value="bd">Business Development</option><option value="proposal">Proposal Writer</option><option value="viewer">Read Only</option></select></label><button className="primary-button"><UserPlus size={16}/> Create invitation</button></form>{message&&<p className="inline-message">{message}</p>}</section><section className="data-panel"><h2>Members</h2><div className="simple-table">{members.map(m=><div className="simple-row" key={m.id}><span>{`${m.user.first_name} ${m.user.last_name}`.trim()||m.user.email}<small>{m.user.email}</small></span><b>{m.role}</b></div>)}</div></section><section className="data-panel"><h2>Invitations</h2><div className="simple-table">{invites.map(i=><div className="simple-row" key={i.id}><span>{i.email}<small>Expires {new Date(i.expires_at).toLocaleDateString()}</small></span><b>{i.status} · {i.role}</b></div>)}</div></section></>}</>;
}
