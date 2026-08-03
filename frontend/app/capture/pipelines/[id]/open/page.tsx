"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { RefreshCw } from "lucide-react";
import { apiGet } from "@/lib/api";

type PipelineItem={id:number;workspace_url?:string;opportunity_detail?:{title?:string}};

export default function PipelineWorkspaceResolver(){
 const params=useParams<{id:string}>();
 const router=useRouter();
 const [error,setError]=useState("");
 useEffect(()=>{let cancelled=false;const timer=window.setTimeout(()=>{apiGet<PipelineItem>(`/pipeline/${encodeURIComponent(params.id)}/`).then(row=>{if(cancelled)return;if(row.workspace_url){router.replace(row.workspace_url);return}setError("This pipeline record does not have a valid opportunity workspace.")}).catch(e=>{if(!cancelled)setError(e instanceof Error?e.message:"Opportunity workspace unavailable")})},0);return()=>{cancelled=true;window.clearTimeout(timer)}},[params.id,router]);
 if(error)return <div className="page-stack"><section className="data-panel table-state"><strong>Opportunity workspace unavailable</strong><p>{error}</p><div className="row-actions"><Link className="primary-button" href="/capture/pipelines">Return to pipeline</Link></div></section></div>;
 return <div className="page-stack"><section className="data-panel table-state"><RefreshCw className="spin"/><strong>Opening opportunity workspace</strong><p>Resolving the canonical opportunity route from the pipeline record.</p></section></div>;
}
