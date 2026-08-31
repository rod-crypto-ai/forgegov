/* eslint-disable @next/next/no-img-element */
"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Building2, ImagePlus, Trash2 } from "lucide-react";
import { apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

const API_BASE=(process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000/api").replace(/\/$/,"");

export function CompanyIdentity({name,organizationId,compact=false,href,className="",showName=true}:{name:string;organizationId?:number|string|null;compact?:boolean;href?:string;className?:string;showName?:boolean;}){
  const [failedSrc,setFailedSrc]=useState("");
  const src=useMemo(()=>organizationId?`${API_BASE}/network/organizations/${organizationId}/logo/`:`${API_BASE}/network/company-logo/?name=${encodeURIComponent(name)}`,[name,organizationId]);
  const failed=failedSrc===src;
  const body=<span className={`company-identity ${compact?"compact":""} ${className}`.trim()}><span className="company-logo-mark">{failed?<Building2/>:<img src={src} alt="" onError={()=>setFailedSrc(src)}/>}</span>{showName&&<span className="company-identity-name">{name}</span>}</span>;
  return href?<Link className="company-identity-link" href={href}>{body}</Link>:body;
}

export function CompanyBrandingPanel(){
  const {session}=useAuth();
  const organization=session?.organization;
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");
  const [version,setVersion]=useState(0);

  async function upload(file:File){
    if(file.size>2*1024*1024){setMessage("Logo must be 2 MB or smaller.");return}
    if(!["image/png","image/jpeg","image/webp"].includes(file.type)){setMessage("Choose a PNG, JPEG, or WebP logo.");return}
    setBusy(true);setMessage("");
    try{
      const encoded=await new Promise<string>((resolve,reject)=>{
        const reader=new FileReader();
        reader.onerror=()=>reject(new Error("Could not read logo image."));
        reader.onload=()=>resolve(String(reader.result||"").split(",",2)[1]||"");
        reader.readAsDataURL(file);
      });
      await apiPost("/network/profile/logo/",{content_type:file.type,content_base64:encoded});
      setVersion(v=>v+1);setMessage("Company logo updated.");
    }catch(error){setMessage(error instanceof Error?error.message:"Company logo could not be updated.")}
    finally{setBusy(false)}
  }

  async function remove(){
    setBusy(true);setMessage("");
    try{await apiPost("/network/profile/logo/",{remove:true});setVersion(v=>v+1);setMessage("Company logo removed.");}
    catch(error){setMessage(error instanceof Error?error.message:"Company logo could not be removed.")}
    finally{setBusy(false)}
  }

  if(!organization)return null;
  return <section className="company-branding-panel" data-logo-version={version}><div className="company-branding-preview"><CompanyIdentity key={version} name={organization.name} organizationId={organization.id}/></div><div><strong>Company logo</strong><p>Shown beside your company name across ForgeGov. PNG, JPEG, or WebP · 2 MB max.</p>{message&&<small>{message}</small>}</div><div className="company-branding-actions"><label className="secondary-button company-logo-upload"><ImagePlus size={15}/>{busy?"Working…":"Upload / replace"}<input disabled={busy} type="file" accept="image/png,image/jpeg,image/webp" onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);e.currentTarget.value=""}}/></label><button className="secondary-button" disabled={busy} onClick={()=>void remove()}><Trash2 size={15}/>Remove</button><Link className="secondary-button" href="/reference/naics">NAICS reference</Link></div></section>;
}
