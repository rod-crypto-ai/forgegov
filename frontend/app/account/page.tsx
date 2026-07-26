"use client";
import { FormEvent, useState } from "react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

export default function AccountPage(){
 const {session,reload}=useAuth(); const [first,setFirst]=useState(session?.user.first_name||""); const [last,setLast]=useState(session?.user.last_name||""); const [message,setMessage]=useState("");
 async function submit(e:FormEvent){e.preventDefault();try{await authFetch("/auth/me/",{method:"PATCH",body:JSON.stringify({first_name:first,last_name:last})});await reload();setMessage("Profile saved.");}catch(error){setMessage(error instanceof Error?error.message:"Save failed");}}
 return <><header className="feature-hero"><div><span className="eyebrow">Account</span><h1>Profile and workspace</h1><p>Manage your personal details and view your active ForgeGov organization.</p></div></header><section className="data-panel account-panel"><form onSubmit={submit} className="advanced-filter-grid"><label><span>First name</span><input value={first} onChange={e=>setFirst(e.target.value)}/></label><label><span>Last name</span><input value={last} onChange={e=>setLast(e.target.value)}/></label><label><span>Email</span><input value={session?.user.email||""} disabled/></label><label><span>Workspace</span><input value={session?.organization.name||""} disabled/></label><label><span>Role</span><input value={session?.role||""} disabled/></label><button className="primary-button">Save profile</button></form>{message&&<p className="inline-message">{message}</p>}</section></>;
}
