"use client";
import { usePathname } from "next/navigation";
import { FormEvent, useState } from "react";
import { MessageSquarePlus, X } from "lucide-react";
import { apiPost } from "@/lib/api";

export function BetaFeedbackButton(){
  const pathname=usePathname(); const [open,setOpen]=useState(false); const [category,setCategory]=useState("issue"); const [message,setMessage]=useState(""); const [status,setStatus]=useState(""); const [busy,setBusy]=useState(false);
  async function submit(e:FormEvent){e.preventDefault();setBusy(true);setStatus("");try{await apiPost("/beta-feedback/",{category,message,page_path:pathname});setMessage("");setStatus("Feedback received — thank you.");}catch(err){setStatus(err instanceof Error?err.message:"Could not send feedback.");}finally{setBusy(false)}}
  return <><button className="beta-feedback-trigger" onClick={()=>setOpen(true)}><MessageSquarePlus size={16}/> Beta feedback</button>{open&&<div className="beta-feedback-panel"><header><div><b>Help improve ForgeGov</b><small>Report an issue or suggest an improvement.</small></div><button onClick={()=>setOpen(false)} aria-label="Close feedback"><X size={18}/></button></header><form onSubmit={submit}><label><span>Type</span><select value={category} onChange={e=>setCategory(e.target.value)}><option value="issue">Issue</option><option value="suggestion">Suggestion</option><option value="ux">User experience</option><option value="data">Data / connector</option><option value="other">Other</option></select></label><label><span>What happened?</span><textarea required minLength={5} value={message} onChange={e=>setMessage(e.target.value)} placeholder="Tell us what you expected and what happened…"/></label><small>Page: {pathname}</small>{status&&<p>{status}</p>}<button disabled={busy||message.trim().length<5}>{busy?"Sending…":"Send feedback"}</button></form></div>}</>
}
