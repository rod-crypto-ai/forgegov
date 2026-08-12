"use client";
import Link from "next/link";
import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { authFetch } from "@/lib/api";

export default function ForgotPasswordPage(){
 const[email,setEmail]=useState("");const[message,setMessage]=useState("");const[busy,setBusy]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();setBusy(true);try{const result=await authFetch<{detail:string}>("/auth/password-reset/request/",{method:"POST",body:JSON.stringify({email})});setMessage(result.detail)}catch(error){setMessage(error instanceof Error?error.message:"Request failed")}finally{setBusy(false)}}
 return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Account recovery</small></div></div><KeyRound size={36}/><h1>Reset your password</h1><p>Enter your ForgeGov email. For security, the response is the same whether or not an account exists.</p><form onSubmit={submit}><label><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email"/></label>{message&&<p className="inline-message">{message}</p>}<button className="primary-button" disabled={busy}>{busy?"Sending…":"Send reset instructions"}</button></form><p className="auth-switch"><Link href="/sign-in">Back to sign in</Link></p></section></main>
}
