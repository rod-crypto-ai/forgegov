"use client";
import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { LockKeyhole } from "lucide-react";
import { authFetch } from "@/lib/api";

function ResetPassword(){
 const params=useSearchParams();const token=params.get("token")||"";const[password,setPassword]=useState("");const[confirm,setConfirm]=useState("");const[message,setMessage]=useState("");const[done,setDone]=useState(false);const[busy,setBusy]=useState(false);
 async function submit(e:FormEvent){e.preventDefault();if(password!==confirm){setMessage("Passwords do not match.");return}setBusy(true);setMessage("");try{const result=await authFetch<{detail:string}>("/auth/password-reset/confirm/",{method:"POST",body:JSON.stringify({token,password})});setDone(true);setMessage(result.detail)}catch(error){setMessage(error instanceof Error?error.message:"Password reset failed")}finally{setBusy(false)}}
 return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Secure password reset</small></div></div><LockKeyhole size={36}/><h1>{done?"Password changed":"Choose a new password"}</h1>{done?<><p>{message}</p><Link className="primary-button auth-link-button" href="/sign-in">Sign in</Link></>:<form onSubmit={submit}><label><span>New password</span><input type="password" minLength={15} value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="new-password"/></label><label><span>Confirm password</span><input type="password" minLength={15} value={confirm} onChange={e=>setConfirm(e.target.value)} required autoComplete="new-password"/></label><small>Minimum 15 characters.</small>{message&&<p className="form-error">{message}</p>}<button className="primary-button" disabled={busy||!token}>{busy?"Changing…":"Change password"}</button></form>}</section></main>
}
export default function ResetPasswordPage(){return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading reset…</p></section></main>}><ResetPassword/></Suspense>}
