"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { CalendarPlus, Check, Mail, MessageSquare, PanelsTopLeft, Send, X } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type MicrosoftStatus = {
  configured:boolean;
  connected:boolean;
  account_email:string;
  default_team_name?:string;
  default_channel_name?:string;
};

type Props = {
  title:string;
  summary?:string;
  sourceUrl?:string;
  deadline?:string;
  agency?:string;
  solicitationNumber?:string;
};

type Mode = "mail"|"calendar"|"teams";

function localDateTime(value?:string){
  if(!value)return "";
  const date=new Date(value);
  if(Number.isNaN(date.getTime()))return "";
  const pad=(n:number)=>String(n).padStart(2,"0");
  return `${date.getFullYear()}-${pad(date.getMonth()+1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function MicrosoftActions({title,summary="",sourceUrl="",deadline="",agency="",solicitationNumber=""}:Props){
  const [status,setStatus]=useState<MicrosoftStatus|null>(null);
  const [open,setOpen]=useState(false);
  const [mode,setMode]=useState<Mode>("mail");
  const [to,setTo]=useState("");
  const [subject,setSubject]=useState(`ForgeGov opportunity: ${title}`);
  const [body,setBody]=useState("");
  const [start,setStart]=useState(localDateTime(deadline));
  const [end,setEnd]=useState("");
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState("");

  useEffect(()=>{let active=true;apiGet<MicrosoftStatus>("/integrations/microsoft/status/").then(row=>{if(active)setStatus(row)}).catch(()=>{if(active)setStatus({configured:false,connected:false,account_email:""})});return()=>{active=false}},[]);

  const defaultBody=useMemo(()=>[
    title,
    agency?`Agency / prime: ${agency}`:"",
    solicitationNumber?`Reference: ${solicitationNumber}`:"",
    deadline?`Deadline: ${new Date(deadline).toLocaleString()}`:"",
    summary?.slice(0,1500),
    sourceUrl?`Source: ${sourceUrl}`:"",
  ].filter(Boolean).join("\n\n"),[title,agency,solicitationNumber,deadline,summary,sourceUrl]);

  function show(next:Mode){setMode(next);setBody(defaultBody);setMessage("");setOpen(true)}
  function changeStart(value:string){setStart(value);const date=new Date(value);if(Number.isNaN(date.getTime())){setEnd("");return;}date.setMinutes(date.getMinutes()+30);setEnd(localDateTime(date.toISOString()))}
  async function submit(){
    setBusy(true);setMessage("");
    try{
      if(mode==="mail")await apiPost("/integrations/microsoft/send-mail/",{to,subject,body});
      if(mode==="calendar")await apiPost("/integrations/microsoft/calendar-event/",{subject,start,end,timezone:Intl.DateTimeFormat().resolvedOptions().timeZone||"UTC",body,attendees:to});
      if(mode==="teams")await apiPost("/integrations/microsoft/teams-message/",{message:body});
      setMessage(mode==="mail"?"Outlook email sent.":mode==="calendar"?"Outlook calendar event created.":"Shared to Microsoft Teams.");
    }catch(error){setMessage(error instanceof Error?error.message:"Microsoft 365 action failed.")}finally{setBusy(false)}
  }

  return <>
    <button className="secondary-button microsoft-action-trigger" onClick={()=>show("mail")}><PanelsTopLeft size={16}/>Microsoft 365</button>
    {open&&<div className="document-viewer-backdrop" role="dialog" aria-modal="true"><div className="record-modal microsoft-action-modal">
      <header><div><span className="eyebrow">CONNECTED APP</span><h2>Microsoft 365</h2><p>{status?.connected?`Connected as ${status.account_email}`:"Connect Outlook and Teams to work without leaving ForgeGov."}</p></div><button className="icon-button" onClick={()=>setOpen(false)}><X/></button></header>
      {!status?.configured?<div className="table-state"><PanelsTopLeft/><strong>Microsoft 365 administrator setup required.</strong><p>Your ForgeGov administrator must add the Microsoft Entra application credentials.</p></div>:!status.connected?<div className="table-state"><PanelsTopLeft/><strong>Connect your Microsoft account</strong><p>Connections are personal and use delegated Microsoft permissions.</p><Link className="primary-button" href="/settings#integrations">Open Connected Apps</Link></div>:<>
        <div className="microsoft-mode-tabs"><button className={mode==="mail"?"active":""} onClick={()=>setMode("mail")}><Mail/>Outlook email</button><button className={mode==="calendar"?"active":""} onClick={()=>setMode("calendar")}><CalendarPlus/>Calendar</button><button className={mode==="teams"?"active":""} onClick={()=>setMode("teams")}><MessageSquare/>Teams</button></div>
        <div className="microsoft-action-form">
          {mode!=="teams"&&<label><span>{mode==="mail"?"Recipients":"Attendees (optional)"}</span><input value={to} onChange={e=>setTo(e.target.value)} placeholder="name@example.com, teammate@example.com"/></label>}
          {mode!=="teams"&&<label><span>Subject</span><input value={subject} onChange={e=>setSubject(e.target.value)}/></label>}
          {mode==="calendar"&&<div className="microsoft-time-grid"><label><span>Start</span><input type="datetime-local" value={start} onChange={e=>changeStart(e.target.value)}/></label><label><span>End</span><input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label></div>}
          {mode==="teams"&&<div className="settings-callout"><MessageSquare/><p>{status.default_team_name&&status.default_channel_name?`Posting to ${status.default_team_name} / ${status.default_channel_name}.`:"Choose a default Team and channel in Settings before sharing."}</p></div>}
          <label><span>{mode==="teams"?"Teams message":"Message / notes"}</span><textarea rows={10} value={body} onChange={e=>setBody(e.target.value)}/></label>
          {message&&<div className="system-banner settings-message"><Check size={16}/>{message}</div>}
        </div>
        <footer><span>ForgeGov never exposes your Microsoft access token to the browser.</span><button className="primary-button" disabled={busy||(mode==="mail"&&!to.trim())||(mode==="calendar"&&(!start||!end))} onClick={()=>void submit()}><Send size={15}/>{busy?"Working…":mode==="mail"?"Send with Outlook":mode==="calendar"?"Create calendar event":"Share to Teams"}</button></footer>
      </>}
    </div></div>}
  </>;
}
