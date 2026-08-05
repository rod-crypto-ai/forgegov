"use client";
import {useEffect,useMemo,useState} from "react";
import {Search,X} from "lucide-react";
import {apiGet} from "@/lib/api";
type Row={code:string;title:string;level:number;parent:string};
export function NaicsSelector({value,onChange}:{value:string[];onChange:(rows:string[])=>void}){
 const [q,setQ]=useState("");const [rows,setRows]=useState<Row[]>([]);const [open,setOpen]=useState(false);
 useEffect(()=>{if(!open)return;const t=window.setTimeout(()=>{void apiGet<{results:Row[]}>(`/reference/naics/?q=${encodeURIComponent(q)}`).then(r=>setRows(r.results))},180);return()=>window.clearTimeout(t)},[q,open]);
 const selected=useMemo(()=>new Set(value),[value]);
 return <div className="naics-selector"><div className="naics-selected">{value.map(code=><span key={code}>{code}<button type="button" onClick={()=>onChange(value.filter(v=>v!==code))}><X size={12}/></button></span>)}<button type="button" className="secondary-button" onClick={()=>setOpen(!open)}>Browse official NAICS</button></div>{open&&<div className="naics-popover"><label><Search size={16}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search code or official title"/></label><div>{rows.map(row=><button type="button" key={row.code} disabled={selected.has(row.code)} onClick={()=>onChange([...value,row.code])}><strong>{row.code}</strong><span>{row.title}</span></button>)}</div></div>}</div>
}
