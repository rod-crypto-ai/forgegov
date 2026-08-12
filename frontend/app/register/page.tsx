"use client";

import Link from "next/link";
import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, CheckCircle2, LockKeyhole, MailCheck, ShieldCheck } from "lucide-react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

type RegistrationConfig={
  mode:string;
  public_registration:boolean;
  business_email_required:boolean;
  terms_version:string;
  privacy_version:string;
  password_min_length:number;
};
type RegisterResult={
  email?:string;
  email_verified:boolean;
  verification_email_sent?:boolean;
  next_step:string;
  pending_organization?:{id:number;name:string}|null;
};

function RegisterForm() {
  const router=useRouter();
  const params=useSearchParams();
  const {reload}=useAuth();
  const invite=params.get("invite")||"";
  const [config,setConfig]=useState<RegistrationConfig|null>(null);
  const [form,setForm]=useState({first_name:"",last_name:"",email:"",password:"",organization_name:"",accept_terms:false,accept_privacy:false});
  const [message,setMessage]=useState("");
  const [loading,setLoading]=useState(false);

  useEffect(()=>{let active=true;authFetch<RegistrationConfig>("/auth/registration-config/").then(row=>{if(active)setConfig(row)}).catch(()=>{});return()=>{active=false}},[]);
  function set(name:string,value:string|boolean){setForm(current=>({...current,[name]:value}));}

  async function submit(e:FormEvent){
    e.preventDefault();
    setLoading(true);
    setMessage("");
    try{
      const result=await authFetch<RegisterResult>("/auth/register/",{
        method:"POST",
        body:JSON.stringify({...form,invitation_token:invite}),
      });
      if(result.email_verified&&result.next_step==="workspace"){
        await reload();
        router.replace("/");
        return;
      }
      router.replace(`/verify-email?email=${encodeURIComponent(result.email||form.email)}`);
    }catch(error){
      setMessage(error instanceof Error?error.message:"Registration failed");
    }finally{
      setLoading(false);
    }
  }

  const controlled=config&&["private_beta","invite_only","closed"].includes(config.mode)&&!invite;
  if(controlled){
    return <main className="auth-page"><section className="auth-card">
      <div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Controlled access</small></div></div>
      <ShieldCheck size={36}/>
      <h1>ForgeGov access is controlled</h1>
      <p>ForgeGov is currently operating with company-controlled registration. New users join through a secure invitation from an approved company workspace.</p>
      <div className="identity-feature-list">
        <span><MailCheck size={16}/> Verified email identity</span>
        <span><Building2 size={16}/> Company-controlled membership</span>
        <span><LockKeyhole size={16}/> Role-based workspace access</span>
      </div>
      <Link className="primary-button auth-link-button" href="/sign-in">Sign in</Link>
      <p className="auth-switch">Need access? Ask your company owner or ForgeGov administrator for an invitation.</p>
    </section></main>
  }

  return <main className="auth-page"><section className="auth-card auth-card-wide">
    <div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Secure GovCon workspace</small></div></div>
    <div className="identity-heading"><ShieldCheck size={34}/><div><h1>{invite?"Join your ForgeGov company":"Create your ForgeGov account"}</h1><p>{invite?"Your invitation binds this account to the company that invited you.":"Create your identity first. ForgeGov will then create your company workspace or route you to an existing company for approval."}</p></div></div>
    <form onSubmit={submit} className="auth-grid">
      <label><span>First name</span><input value={form.first_name} onChange={e=>set("first_name",e.target.value)} required autoComplete="given-name"/></label>
      <label><span>Last name</span><input value={form.last_name} onChange={e=>set("last_name",e.target.value)} required autoComplete="family-name"/></label>
      <label className="full"><span>{config?.business_email_required&&!invite?"Business email":"Work email"}</span><input type="email" value={form.email} onChange={e=>set("email",e.target.value)} required autoComplete="email"/><small>{invite?"Use the same email address that received the invitation.":"Your email is verified before workspace access is activated."}</small></label>
      {!invite&&<label className="full"><span>Company name</span><input value={form.organization_name} onChange={e=>set("organization_name",e.target.value)} required placeholder="Howard Dynamics" autoComplete="organization"/><small>If your verified email domain already belongs to a ForgeGov company, you will request access instead of creating a duplicate company.</small></label>}
      <label className="full"><span>Password</span><input type="password" value={form.password} onChange={e=>set("password",e.target.value)} required minLength={config?.password_min_length||15} autoComplete="new-password"/><small>Use at least {config?.password_min_length||15} characters. ForgeGov does not require arbitrary symbol or capitalization patterns.</small></label>
      <div className="full auth-consent-box">
        <label><input type="checkbox" checked={form.accept_terms} onChange={e=>set("accept_terms",e.target.checked)} required/><span>I agree to the <Link href="/terms" target="_blank">ForgeGov Terms of Use</Link>.</span></label>
        <label><input type="checkbox" checked={form.accept_privacy} onChange={e=>set("accept_privacy",e.target.checked)} required/><span>I acknowledge the <Link href="/privacy" target="_blank">ForgeGov Privacy Notice</Link>.</span></label>
      </div>
      {message&&<p className="form-error full">{message}</p>}
      <button className="primary-button full" disabled={loading}>{loading?"Securing account…":invite?"Accept invitation & create account":"Create secure account"}</button>
    </form>
    <div className="identity-trust-row"><span><CheckCircle2 size={15}/> Email verification</span><span><CheckCircle2 size={15}/> Expiring invitations</span><span><CheckCircle2 size={15}/> Security audit trail</span></div>
    <p className="auth-switch">Already registered? <Link href="/sign-in">Sign in</Link></p>
  </section></main>;
}

export default function RegisterPage() {
  return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading secure registration…</p></section></main>}><RegisterForm/></Suspense>;
}
