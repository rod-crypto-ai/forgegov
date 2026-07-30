"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, Building2, CalendarSearch, Database, ExternalLink, Network, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { apiGet } from "@/lib/api";

type Row=Record<string,unknown>;
const money=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0});
function text(v:unknown,fallback="—"){return v===null||v===undefined||v===""?fallback:String(v)}

export default function IntelligenceEntityPage(){
 const params=useParams<{entityType:string;entityId:string}>();const type=decodeURIComponent(params.entityType);const id=decodeURIComponent(params.entityId);const[rows,setRows]=useState<Row[]>([]);const[message,setMessage]=useState("Loading intelligence workspace…");
 const load=useCallback(async()=>{setMessage("Refreshing connected intelligence…");try{let endpoint="";if(type==="agency")endpoint=`/intelligence/agencies/?q=${encodeURIComponent(id)}`;else if(type==="forecast")endpoint=`/intelligence/forecasts/sources/?q=${encodeURIComponent(id)}`;else if(type==="award")endpoint=`/live/usaspending/awards/?q=${encodeURIComponent(id)}&limit=25`;else endpoint=`/live/usaspending/vehicles/?q=${encodeURIComponent(id)}&limit=25`;const data=await apiGet<{results?:Row[]}>(endpoint);setRows(data.results??[]);setMessage(`${data.results?.length??0} connected records loaded.`)}catch(e){setMessage(e instanceof Error?e.message:"Intelligence workspace could not be loaded")}},[id,type]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 const Icon=type==="agency"?Building2:type==="forecast"?CalendarSearch:type==="vehicle"?Network:Database;
 return <><header className="feature-hero entity-workspace-hero"><div><Link className="detail-back" href="/"><ArrowLeft size={16}/>Back to ForgeGov</Link><span className="eyebrow">{type.toUpperCase()} INTELLIGENCE WORKSPACE</span><h1>{id}</h1><p>Related public records, market signals, and official-source context gathered into one ForgeGov view.</p></div><button className="secondary-button" onClick={()=>void load()}><RefreshCw size={16}/>Refresh intelligence</button></header><p className="inline-message">{message}</p>
 <section className="entity-workspace-grid">{rows.map((row,index)=><article className="entity-record-card" key={index}><Icon/><div><span>{text(row["Award ID"]??row.agency_code??row.status??row["Awarding Agency"],type)}</span><h3>{text(row.name??row.agency??row["Description"]??row["Recipient Name"]??row["Award ID"]??row.title,id)}</h3><p>{text(row.description??row.summary??row["Description"]??row.coverage,"Connected public intelligence record")}</p><div className="entity-record-meta"><span>{row["Award Amount"]!==undefined?money.format(Number(row["Award Amount"])):text(row.obligated_amount,"")}</span><span>{text(row.naics??row["NAICS Code"],"")}</span></div></div>{row.source_url||row.forecast_url?<a className="icon-button" href={text(row.source_url??row.forecast_url)} target="_blank" rel="noreferrer"><ExternalLink size={16}/></a>:null}</article>)}</section>
 {!rows.length&&<div className="table-state"><Icon size={32}/><strong>No connected records were returned</strong><p>ForgeGov preserved this workspace so more intelligence can be linked as data is ingested.</p></div>}</>;
}
