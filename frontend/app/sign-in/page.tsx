"use client";
import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ShieldCheck } from "lucide-react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

function SignInForm() {
  const router = useRouter(); const params = useSearchParams(); const { reload } = useAuth();
  const [email,setEmail]=useState(""); const [password,setPassword]=useState(""); const [message,setMessage]=useState(""); const [loading,setLoading]=useState(false);
  async function submit(e:FormEvent){e.preventDefault();setLoading(true);setMessage("");try{await authFetch("/auth/login/",{method:"POST",body:JSON.stringify({email,password})});await reload();const requested=params.get("next");const destination=requested?.startsWith("/")&&!requested.startsWith("//")?requested:"/";router.replace(destination);}catch(error){setMessage(error instanceof Error?error.message:"Sign in failed");}finally{setLoading(false);}}
  return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Secure GovCon workspace</small></div></div><ShieldCheck size={34}/><h1>Sign in to ForgeGov</h1><p>Access your organization’s opportunities, pursuits, tasks, files, and capture intelligence.</p><form onSubmit={submit}><label><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email"/></label><label><span>Password</span><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label>{message&&<p className="form-error">{message}</p>}<button className="primary-button" disabled={loading}>{loading?"Signing in…":"Sign in"}</button></form><p className="auth-switch">New to ForgeGov? <Link href="/register">Create an account</Link></p></section></main>;
}


export default function SignInPage() {
  return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading sign in…</p></section></main>}><SignInForm /></Suspense>;
}
