"use client";
import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

function RegisterForm() {
  const router=useRouter(); const params=useSearchParams(); const {reload}=useAuth();
  const [form,setForm]=useState({first_name:"",last_name:"",email:"",password:"",organization_name:""});
  const [message,setMessage]=useState(""); const [loading,setLoading]=useState(false);
  function set(name:string,value:string){setForm(current=>({...current,[name]:value}));}
  async function submit(e:FormEvent){e.preventDefault();setLoading(true);setMessage("");try{await authFetch("/auth/register/",{method:"POST",body:JSON.stringify({...form,invitation_token:params.get("invite")||""})});await reload();router.replace("/");}catch(error){setMessage(error instanceof Error?error.message:"Registration failed");}finally{setLoading(false);}}
  return <main className="auth-page"><section className="auth-card auth-card-wide"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Government contracting intelligence</small></div></div><h1>{params.get("invite")?"Join your ForgeGov team":"Register a new company"}</h1><p>The first account creates and owns a new company workspace. Existing company workspaces are invitation-only.</p><form onSubmit={submit} className="auth-grid"><label><span>First name</span><input value={form.first_name} onChange={e=>set("first_name",e.target.value)} required/></label><label><span>Last name</span><input value={form.last_name} onChange={e=>set("last_name",e.target.value)} required/></label><label className="full"><span>Email</span><input type="email" value={form.email} onChange={e=>set("email",e.target.value)} required/></label>{!params.get("invite")&&<label className="full"><span>Organization</span><input value={form.organization_name} onChange={e=>set("organization_name",e.target.value)} required placeholder="Howard Dynamics"/></label>}<label className="full"><span>Password</span><input type="password" value={form.password} onChange={e=>set("password",e.target.value)} required minLength={8}/></label>{message&&<p className="form-error full">{message}</p>}<button className="primary-button full" disabled={loading}>{loading?"Creating workspace…":"Create secure account"}</button></form><p className="auth-switch">Already registered? <Link href="/sign-in">Sign in</Link></p></section></main>;
}


export default function RegisterPage() {
  return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading registration…</p></section></main>}><RegisterForm /></Suspense>;
}
