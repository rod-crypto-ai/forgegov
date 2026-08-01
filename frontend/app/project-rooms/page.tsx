"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, FolderKanban, Plus, ShieldCheck, Users } from "lucide-react";
import { apiGet, apiPost, normalizeList } from "@/lib/api";

type Room={id:number;name:string;description:string;status:string;owner_organization_name:string;partners:Array<{id:number;organization_name:string;access_level:string;can_view_pricing:boolean}>};

export default function ProjectRoomsPage(){
  const [rooms,setRooms]=useState<Room[]>([]);const[name,setName]=useState("");const[description,setDescription]=useState("");const[message,setMessage]=useState("Loading secure collaboration rooms…");
  const load=useCallback(async()=>{try{const data=await apiGet<Room[]|{results:Room[]}>("/project-rooms/?page_size=100");setRooms(normalizeList<Room>(data));setMessage("")}catch(error){setMessage(error instanceof Error?error.message:"Could not load Project Rooms")}},[]);
  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
  async function createRoom(event:FormEvent){event.preventDefault();if(!name.trim())return;try{await apiPost("/project-rooms/",{name,description,status:"planning"});setName("");setDescription("");setMessage("Project Room created.");await load()}catch(error){setMessage(error instanceof Error?error.message:"Could not create Project Room")}}
  return <><header className="feature-hero"><div><span className="eyebrow">Secure multi-company collaboration</span><h1>Project Rooms</h1><p>Bring internal teams and invited partner companies together around one opportunity without exposing either company’s private workspace.</p></div><div className="source-health-pill live"><span/>Tenant isolated</div></header>
  <section className="release-four-summary"><div><span>Rooms</span><strong>{rooms.length}</strong></div><div><span>Security</span><strong>Scoped access</strong></div><div><span>Partners</span><strong>{rooms.reduce((sum,row)=>sum+row.partners.length,0)}</strong></div><div><span>AI context</span><strong>Room aware</strong></div></section>
  <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CREATE ROOM</span><h2>Start a secure project workspace</h2></div><ShieldCheck/></div><form className="advanced-filter-grid" onSubmit={createRoom}><label><span>Room name</span><input value={name} onChange={e=>setName(e.target.value)} placeholder="Army vehicle maintenance pursuit" required/></label><label><span>Description</span><input value={description} onChange={e=>setDescription(e.target.value)} placeholder="Capture, teaming, proposal, and submission workspace"/></label><button className="primary-button"><Plus size={16}/>Create Project Room</button></form>{message&&<p className="inline-message">{message}</p>}</section>
  <section className="source-card-grid">{rooms.map(room=><article className="source-card" key={room.id}><FolderKanban/><div><span>{room.status}</span><h3>{room.name}</h3><p>{room.description||"Secure opportunity collaboration room."}</p><small><Building2 size={13}/> {room.owner_organization_name} · <Users size={13}/> {room.partners.length} partner companies</small></div><div>{room.partners.slice(0,3).map(p=><span className="status-badge" key={p.id}>{p.organization_name} · {p.access_level}</span>)}</div></article>)}</section></>;
}
