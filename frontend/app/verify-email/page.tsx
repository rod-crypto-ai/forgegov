"use client";
import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, MailCheck, ShieldAlert } from "lucide-react";
import { authFetch } from "@/lib/api";

function VerifyEmail(){
  const params=useSearchParams();
  const token=params.get("token")||"";
  const email=params.get("email")||"";
  const [state,setState]=useState<"waiting"|"verifying"|"verified"|"pending"|"error">(token?"verifying":"waiting");
  const [message,setMessage]=useState(token?"Verifying your secure link…":"Check your inbox for the ForgeGov verification email.");
  const [busy,setBusy]=useState(false);

  useEffect(()=>{if(!token)return;let active=true;authFetch<{next_step:string}>("/auth/verify-email/",{method:"POST",body:JSON.stringify({token})}).then(result=>{if(!active)return;if(result.next_step==="pending_organization_approval"){setState("pending");setMessage("Your email is verified. Your company owner or administrator must approve your workspace access.");}else{setState("verified");setMessage("Email verified. Your ForgeGov identity is active.");}}).catch(error=>{if(active){setState("error");setMessage(error instanceof Error?error.message:"Verification failed.");}});return()=>{active=false}},[token]);

  async function resend(){if(!email)return;setBusy(true);try{await authFetch("/auth/resend-verification/",{method:"POST",body:JSON.stringify({email})});setMessage("If your account is eligible, a new verification email has been sent.");}catch(error){setMessage(error instanceof Error?error.message:"Could not resend verification.")}finally{setBusy(false)}}

  const Icon=state==="verified"?CheckCircle2:state==="error"?ShieldAlert:MailCheck;
  return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Identity verification</small></div></div><Icon size={38}/><h1>{state==="verified"?"Email verified":state==="pending"?"Company approval pending":state==="error"?"Verification problem":"Verify your email"}</h1><p>{message}</p>{state==="waiting"&&email&&<button className="secondary-button" disabled={busy} onClick={()=>void resend()}>{busy?"Sending…":"Resend verification email"}</button>}{(state==="verified"||state==="pending")&&<Link className="primary-button auth-link-button" href="/sign-in">Continue to sign in</Link>}{state==="error"&&<Link className="secondary-button auth-link-button" href="/register">Return to registration</Link>}</section></main>;
}
export default function VerifyEmailPage(){return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading verification…</p></section></main>}><VerifyEmail/></Suspense>}
