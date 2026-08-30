"use client";

import { useEffect, useState } from "react";
import { Search } from "lucide-react";
import { apiGet } from "@/lib/api";

type Row={code:string;title:string;level:number;parent?:string|null};
type Result={version:string;source:string;source_url:string;total_reference_records:number;count:number;results:Row[]};

export default function NaicsReferencePage(){
  const [q,setQ]=useState("");
  const [level,setLevel]=useState("");
  const [data,setData]=useState<Result|null>(null);
  const [error,setError]=useState("");
  useEffect(()=>{
    let active=true;
    const timer=window.setTimeout(()=>{
      const params=new URLSearchParams({limit:"250"});if(q.trim())params.set("q",q.trim());if(level)params.set("level",level);
      apiGet<Result>(`/reference/naics/?${params}`).then(row=>{if(active){setData(row);setError("")}}).catch(err=>{if(active)setError(err instanceof Error?err.message:"NAICS reference could not be loaded.")});
    },180);
    return()=>{active=false;window.clearTimeout(timer)};
  },[q,level]);
  return <div className="page-stack naics-reference-page"><section className="page-hero"><div><span className="eyebrow">OFFICIAL REFERENCE</span><h1>2022 NAICS</h1><p>Complete current U.S. Census NAICS hierarchy for ForgeGov company profiles, opportunity filters, teaming, and market analysis.</p></div></section><section className="data-panel"><div className="naics-reference-controls"><label><span>Search</span><div className="naics-picker-input"><Search size={15}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="541330, engineering, vehicle repair…"/></div></label><label><span>Level</span><select value={level} onChange={e=>setLevel(e.target.value)}><option value="">All levels</option>{[2,3,4,5,6].map(n=><option key={n} value={n}>{n}-digit</option>)}</select></label></div>{error&&<p className="inline-message">{error}</p>}{data&&<p className="panel-note">Official NAICS {data.version} · {data.total_reference_records.toLocaleString()} hierarchy records · U.S. Census Bureau</p>}<div className="naics-reference-table">{data?.results.map(row=><article key={row.code}><strong>{row.code}</strong><div><b>{row.title}</b><small>{row.level}-digit level{row.parent?` · parent ${row.parent}`:""}</small></div></article>)}</div></section></div>;
}
