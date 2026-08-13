"use client";

import Link from "next/link";
import { FormEvent, Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { authFetch } from "@/lib/api";
import { authenticationOptions, serializeCredential } from "@/lib/webauthn";
import { useAuth } from "@/components/auth-provider";

type LoginResult={mfa_required?:boolean;mfa_enrollment_required?:boolean;challenge_token?:string;methods?:string[]};
type PasskeyOptions={challenge_token:string;options:{challenge:string;allowCredentials?:Array<{id:string;type:PublicKeyCredentialType;transports?:AuthenticatorTransport[]}>;[key:string]:unknown}};
type TotpEnrollment={secret:string;provisioning_uri:string;device_id:number};

function SignInForm() {
  const router=useRouter();
  const params=useSearchParams();
  const {reload}=useAuth();
  const [email,setEmail]=useState("");
  const [password,setPassword]=useState("");
  const [message,setMessage]=useState("");
  const [loading,setLoading]=useState(false);
  const [challenge,setChallenge]=useState("");
  const [methods,setMethods]=useState<string[]>([]);
  const [method,setMethod]=useState("totp");
  const [code,setCode]=useState("");
  const [enrollment,setEnrollment]=useState<TotpEnrollment|null>(null);
  const [recoveryCodes,setRecoveryCodes]=useState<string[]>([]);

  async function finish(){await reload();const requested=params.get("next");router.replace(requested?.startsWith("/")&&!requested.startsWith("//")?requested:"/");}

  async function submit(e:FormEvent){
    e.preventDefault();setLoading(true);setMessage("");
    try{
      const result=await authFetch<LoginResult>("/auth/login/",{method:"POST",body:JSON.stringify({email,password})});
      if(result.mfa_enrollment_required&&result.challenge_token){setChallenge(result.challenge_token);const setup=await authFetch<TotpEnrollment>("/auth/mfa/enroll/totp/setup/",{method:"POST",body:JSON.stringify({challenge_token:result.challenge_token})});setEnrollment(setup);return;}
      if(result.mfa_required&&result.challenge_token){setChallenge(result.challenge_token);setMethods(result.methods||[]);setMethod(result.methods?.includes("totp")?"totp":result.methods?.includes("recovery_code")?"recovery_code":"passkey");return;}
      await finish();
    }catch(error){setMessage(error instanceof Error?error.message:"Sign in failed");}
    finally{setLoading(false)}
  }

  async function verifyCode(e:FormEvent){e.preventDefault();setLoading(true);setMessage("");try{await authFetch("/auth/mfa/verify/",{method:"POST",body:JSON.stringify({challenge_token:challenge,method,code})});await finish();}catch(error){setMessage(error instanceof Error?error.message:"MFA verification failed")}finally{setLoading(false)}}

  async function verifyPasskey(){setLoading(true);setMessage("");try{const row=await authFetch<PasskeyOptions>("/auth/mfa/passkey/options/",{method:"POST",body:JSON.stringify({challenge_token:challenge})});const credential=await navigator.credentials.get({publicKey:authenticationOptions(row.options)});if(!credential)throw new Error("Passkey authentication was cancelled.");await authFetch("/auth/mfa/passkey/verify/",{method:"POST",body:JSON.stringify({challenge_token:row.challenge_token,credential:serializeCredential(credential as PublicKeyCredential)})});await finish();}catch(error){setMessage(error instanceof Error?error.message:"Passkey authentication failed")}finally{setLoading(false)}}

  async function finishEnrollment(e:FormEvent){e.preventDefault();setLoading(true);setMessage("");try{const result=await authFetch<{recovery_codes:string[]}>("/auth/mfa/enroll/totp/confirm/",{method:"POST",body:JSON.stringify({challenge_token:challenge,code})});setRecoveryCodes(result.recovery_codes||[]);setEnrollment(null);setCode("");}catch(error){setMessage(error instanceof Error?error.message:"MFA enrollment failed")}finally{setLoading(false)}}

  if(recoveryCodes.length>0)return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>MFA enrollment complete</small></div></div><ShieldCheck size={36}/><h1>Save your recovery codes</h1><p>Each code works once. Store them somewhere separate from your password and authenticator app.</p><div className="recovery-code-grid">{recoveryCodes.map(row=><code key={row}>{row}</code>)}</div><button className="primary-button" onClick={()=>void finish()}>Continue to ForgeGov</button></section></main>;

  if(enrollment)return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Company-required MFA</small></div></div><ShieldCheck size={36}/><h1>Set up your authenticator</h1><p>Your company requires MFA before workspace access. Add ForgeGov to your authenticator app using this setup URI or manual secret.</p><code className="auth-uri">{enrollment.provisioning_uri}</code><div className="secret-box"><span>Manual secret</span><b>{enrollment.secret}</b></div><form onSubmit={finishEnrollment}><label><span>6-digit authenticator code</span><input value={code} onChange={e=>setCode(e.target.value)} inputMode="numeric" autoComplete="one-time-code" required/></label>{message&&<p className="form-error">{message}</p>}<button className="primary-button" disabled={loading}>{loading?"Verifying…":"Enable MFA & sign in"}</button></form></section></main>;

  if(challenge)return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Multi-factor authentication</small></div></div><ShieldCheck size={36}/><h1>Verify it&apos;s you</h1><p>Your password was accepted. Complete a second authentication factor to enter ForgeGov.</p>{methods.includes("passkey")&&<button className="primary-button" onClick={()=>void verifyPasskey()} disabled={loading}><KeyRound size={16}/>Use a passkey</button>}{(methods.includes("totp")||methods.includes("recovery_code"))&&<form onSubmit={verifyCode}><label><span>Method</span><select value={method} onChange={e=>setMethod(e.target.value)}>{methods.includes("totp")&&<option value="totp">Authenticator app</option>}{methods.includes("recovery_code")&&<option value="recovery_code">Recovery code</option>}</select></label><label><span>{method==="totp"?"6-digit code":"Recovery code"}</span><input value={code} onChange={e=>setCode(e.target.value)} autoComplete="one-time-code" required/></label>{message&&<p className="form-error">{message}</p>}<button className="secondary-button" disabled={loading}>{loading?"Verifying…":"Verify & sign in"}</button></form>}<button className="text-button" onClick={()=>{setChallenge("");setCode("");setMessage("")}}>Use another account</button></section></main>;

  return <main className="auth-page"><section className="auth-card"><div className="auth-brand"><span className="forge-logo"><span>F</span>G</span><div><b>FORGEGOV</b><small>Secure GovCon workspace</small></div></div><ShieldCheck size={36}/><h1>Sign in to ForgeGov</h1><p>Access your company&apos;s contracting intelligence, capture work, pricing, proposals, and collaboration workspace.</p><form onSubmit={submit}><label><span>Email</span><input type="email" value={email} onChange={e=>setEmail(e.target.value)} required autoComplete="email"/></label><label><span>Password</span><input type="password" value={password} onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label><div className="auth-password-row"><Link href="/forgot-password">Forgot password?</Link></div>{message&&<p className="form-error">{message}</p>}<button className="primary-button" disabled={loading}><LockKeyhole size={16}/>{loading?"Signing in…":"Sign in securely"}</button></form><p className="auth-switch">New to ForgeGov? <Link href="/register">Create an account</Link></p></section></main>;
}

export default function SignInPage(){return <Suspense fallback={<main className="auth-page"><section className="auth-card"><p>Loading sign in…</p></section></main>}><SignInForm/></Suspense>}
