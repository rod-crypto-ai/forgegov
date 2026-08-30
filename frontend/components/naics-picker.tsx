"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { apiGet } from "@/lib/api";

type NaicsRow={code:string;title:string;level:number;parent?:string|null};
type NaicsResponse={version:string;results:NaicsRow[]};

export function NaicsPicker({value,onChange,label="NAICS",placeholder="Search code or industry title"}:{value:string;onChange:(value:string)=>void;label?:string;placeholder?:string;}){
  const query=value;
  const [rows,setRows]=useState<NaicsRow[]>([]);
  const [open,setOpen]=useState(false);
  useEffect(()=>{
    const q=query.trim();
    if(q.length<2){const timer=window.setTimeout(()=>setRows([]),0);return()=>window.clearTimeout(timer)}
    let active=true;
    const timer=window.setTimeout(()=>{apiGet<NaicsResponse>(`/reference/naics/?q=${encodeURIComponent(q)}&limit=25`).then(data=>{if(active){setRows(data.results??[]);setOpen(true)}}).catch(()=>{});},180);
    return()=>{active=false;window.clearTimeout(timer)};
  },[query]);
  return <label className="naics-picker"><span>{label}</span><div className="naics-picker-input"><Search size={15}/><input value={query} onChange={e=>onChange(e.target.value)} onFocus={()=>setOpen(true)} placeholder={placeholder}/></div>{open&&rows.length>0&&<div className="naics-picker-menu">{rows.map(row=><button type="button" key={row.code} onMouseDown={e=>e.preventDefault()} onClick={()=>{onChange(row.code);setOpen(false)}}><strong>{row.code}</strong><span>{row.title}</span></button>)}</div>}</label>;
}
