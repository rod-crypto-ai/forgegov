"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CheckCircle2, ChevronRight, Circle, Plus, RefreshCw, Save, Trash2 } from "lucide-react";
import Link from "next/link";
import { apiDelete, apiGet, apiPatch, apiPost, normalizeList } from "@/lib/api";

type Opportunity = { id:number; source_id?:string; source?:string; title:string; agency?:string; solicitation_number?:string; response_deadline?:string; source_url?:string };
type Pipeline = { id:number; workspace_url?:string; teaming_workspace_url?:string; project_room?:number|null; project_room_name?:string; stage:string; owner?:number|null; owner_name?:string; probability_of_win:number; estimated_value?:string; next_action?:string; follow_up_date?:string|null; priority?:string; assigned_team?:string; notes?:string; opportunity_detail:Opportunity };
type Member = {id:number;user:{id:number;email:string;first_name:string;last_name:string};role:string;job_title:string};
type ProjectRoomOption={id:number;name:string;opportunity?:number|null;status:string};
type Pursuit = { id:number; title:string; stage:string; probability_of_win:number; estimated_value?:string; due_date?:string; next_action?:string; incumbent?:string };
type Task = { id:number; title:string; description?:string; due_at?:string; completed:boolean; pipeline_item?:number };
type SavedSearch = { id:number; name:string; filters:Record<string,string>; alert_frequency:string; enabled:boolean };
const stages=["discovered","reviewing","qualified","bid_decision","capture","teaming","proposal","submitted","awarded","lost","no_bid","archived"];
const pursuitStages=["triage","qualify","bid_decision","capture","proposal","submitted","awarded","lost","no_bid","archived"];
const localDateTime=(value?:string)=>{if(!value)return "";const date=new Date(value);if(Number.isNaN(date.getTime()))return "";return new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16)};
const human=(v:string)=>v.replaceAll("_"," ").replace(/\b\w/g,c=>c.toUpperCase());
const money=new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0});
const opportunityHref=(opportunity:Opportunity)=>{const sourceId=String(opportunity.source_id??"");if(opportunity.source==="grants.gov"||sourceId.startsWith("grants.gov:")){const id=sourceId.replace(/^grants\.gov:/,"");return id?`/opportunities/federal-grants/${encodeURIComponent(id)}`:"/opportunities/federal-grants"}if(opportunity.source==="sba-subnet"||sourceId.startsWith("sba-subnet:"))return sourceId?`/opportunities/subcontracting/${encodeURIComponent(sourceId)}`:"/opportunities/subcontracting";return sourceId?`/opportunities/federal-contracts/${encodeURIComponent(sourceId)}`:"/opportunities/federal-contracts"};

export function PipelineWorkspace(){
 const [rows,setRows]=useState<Pipeline[]>([]);const [members,setMembers]=useState<Member[]>([]);const [rooms,setRooms]=useState<ProjectRoomOption[]>([]);const [error,setError]=useState("");const [loading,setLoading]=useState(true);const [creating,setCreating]=useState<number|null>(null);
 const load=useCallback(async()=>{setLoading(true);try{const[pipelineData,memberData,roomData]=await Promise.all([apiGet<Pipeline[]>("/pipeline/?page_size=250"),apiGet<Member[]>("/team/members/"),apiGet<ProjectRoomOption[]>("/project-rooms/?page_size=250")]);setRows(normalizeList(pipelineData));setMembers(normalizeList(memberData));setRooms(normalizeList(roomData));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load pipeline")}finally{setLoading(false)}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function update(id:number,payload:Record<string,unknown>){try{await apiPatch(`/pipeline/${id}/`,payload);await load()}catch(e){setError(e instanceof Error?e.message:"Update failed")}}
 async function setRoom(row:Pipeline,value:string){try{if(value==="create"){setCreating(row.id);await apiPost(`/workflow/pipeline/${row.id}/project-room/`,{action:"create",name:`${row.opportunity_detail.title} Teaming Workspace`})}else if(value){await apiPost(`/workflow/pipeline/${row.id}/project-room/`,{action:"link",project_room:Number(value)})}else{await apiPost(`/workflow/pipeline/${row.id}/project-room/`,{action:"unlink"})}await load()}catch(e){setError(e instanceof Error?e.message:"Project Room update failed")}finally{setCreating(null)}}
 async function pursue(id:number){try{await apiPost(`/workflow/pipeline/${id}/create-pursuit/`,{});await load();setError("Pursuit created and linked.")}catch(e){setError(e instanceof Error?e.message:"Could not create pursuit")}}
 async function remove(id:number,title:string){if(!window.confirm(`Remove ${title} from the pipeline?`))return;try{await apiDelete(`/pipeline/${id}/`);await load();setError("")}catch(e){setError(e instanceof Error?e.message:"Could not remove pipeline item")}}
 const total=useMemo(()=>rows.reduce((s,r)=>s+Number(r.estimated_value??0),0),[rows]);
 return <><header className="module-header"><div><span className="eyebrow">Capture operations</span><h1>Pipeline</h1><p>Qualify opportunities and launch dedicated teaming workspaces without breaking the opportunity route.</p></div><button className="secondary-button" onClick={load}><RefreshCw size={16}/> Refresh</button></header>
 <section className="workspace-summary"><div><span>Pipeline items</span><strong>{rows.length}</strong><small>Live database records</small></div><div><span>Estimated value</span><strong>{money.format(total)}</strong><small>Across valued opportunities</small></div><div><span>In capture</span><strong>{rows.filter(r=>["capture","teaming","proposal"].includes(r.stage)).length}</strong><small>Active capture work</small></div><div><span>Teaming rooms</span><strong>{rows.filter(r=>r.project_room).length}</strong><small>Linked collaboration workspaces</small></div></section>
 {error&&<div className="system-banner warning">{error}</div>}
 <section className="data-panel">{loading?<div className="table-state"><RefreshCw className="spin"/><strong>Loading pipeline</strong></div>:!rows.length?<div className="table-state"><strong>No pipeline items yet</strong><p>Search opportunities and use Add to pipeline.</p></div>:<div className="pipeline-list">{rows.map(r=><article className="pipeline-row" key={r.id}><div><span className="eyebrow">{r.opportunity_detail.solicitation_number||"Opportunity"}</span><Link className="pipeline-title-link" href={`/capture/pipelines/${r.id}/open`}><h3>{r.opportunity_detail.title}</h3></Link><p>{r.opportunity_detail.agency||"Agency unavailable"}</p></div><label><span>Stage</span><select value={r.stage} onChange={e=>void update(r.id,{stage:e.target.value})}>{stages.map(s=><option key={s} value={s}>{human(s)}</option>)}</select></label><label><span>Owner</span><select value={r.owner??""} onChange={e=>void update(r.id,{owner:e.target.value?Number(e.target.value):null})}><option value="">Unassigned</option>{members.map(m=><option key={m.id} value={m.user.id}>{[m.user.first_name,m.user.last_name].filter(Boolean).join(" ")||m.user.email}</option>)}</select></label><label><span>Priority</span><select value={r.priority??"medium"} onChange={e=>void update(r.id,{priority:e.target.value})}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label><label className="pipeline-room-select"><span>Teaming workspace</span><select value={r.project_room??""} disabled={creating===r.id} onChange={e=>void setRoom(r,e.target.value)}><option value="">No Project Room</option>{rooms.filter(room=>!room.opportunity||room.opportunity===r.opportunity_detail.id).map(room=><option key={room.id} value={room.id}>{room.name}</option>)}<option value="create">＋ Create new Project Room</option></select></label><label><span>Follow-up</span><input type="date" value={r.follow_up_date??""} onChange={e=>void update(r.id,{follow_up_date:e.target.value||null})}/></label><label><span>Win probability</span><input type="number" min="0" max="100" value={r.probability_of_win} onChange={e=>void update(r.id,{probability_of_win:Number(e.target.value)})}/></label><label className="pipeline-next-action"><span>Next action</span><input value={r.next_action??""} onBlur={e=>void update(r.id,{next_action:e.target.value})} onChange={e=>setRows(x=>x.map(a=>a.id===r.id?{...a,next_action:e.target.value}:a))}/></label><div className="row-actions"><Link className="secondary-button" href={`/capture/pipelines/${r.id}/open`}>Open opportunity</Link>{r.teaming_workspace_url?<Link className="primary-button" href={r.teaming_workspace_url}>Open teaming workspace</Link>:null}<button className="secondary-button" onClick={()=>void pursue(r.id)}>Create pursuit <ChevronRight size={15}/></button><button className="icon-button danger-button" title="Remove from pipeline" onClick={()=>void remove(r.id,r.opportunity_detail.title)}><Trash2 size={17}/></button></div></article>)}</div>}</section></>;
}

export function PursuitsWorkspace(){
 const [loading,setLoading]=useState(true);const [busy,setBusy]=useState<number|null>(null);const dialogRef=useRef<HTMLDialogElement>(null);
 const [rows,setRows]=useState<Pursuit[]>([]);const [error,setError]=useState("");const[selected,setSelected]=useState<Pursuit|null>(null);const [dragging,setDragging]=useState<number|null>(null);const [dragStage,setDragStage]=useState("");const [now]=useState(()=>Date.now());
 const load=useCallback(async()=>{setLoading(true);try{setRows(normalizeList(await apiGet<Pursuit[]>("/pursuits/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load pursuits")}finally{setLoading(false)}},[]);
 const selectedId=selected?.id;
 useEffect(()=>{const dialog=dialogRef.current;if(selectedId&&dialog&&!dialog.open)dialog.showModal();return()=>{if(dialog?.open)dialog.close()}},[selectedId]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function patch(id:number,payload:Record<string,unknown>){if(busy!==null)return;setBusy(id);setError("");try{const updated=await apiPatch<Pursuit>(`/pursuits/${id}/`,payload);setRows(current=>current.map(row=>row.id===id?updated:row));setSelected(current=>current?.id===id?updated:current)}catch(e){setError(e instanceof Error?e.message:"Update failed")}finally{setBusy(null)}}
 async function movePursuit(id:number,stage:string){setDragging(null);setDragStage("");await patch(id,{stage})}
 const active=rows.filter(r=>!["awarded","lost","no_bid","archived"].includes(r.stage));
 const totalValue=active.reduce((sum,row)=>sum+Number(row.estimated_value??0),0);
 const weighted=active.reduce((sum,row)=>sum+(Number(row.estimated_value??0)*(Number(row.probability_of_win??0)/100)),0);
 const overdue=active.filter(row=>row.due_date&&new Date(row.due_date).getTime()<now).length;
 const dueSoon=active.filter(row=>row.due_date&&new Date(row.due_date).getTime()-now<1000*60*60*24*14&&new Date(row.due_date).getTime()>=now).length;
 return <><header className="module-header"><div><span className="eyebrow">Capture management</span><h1>Pursuits</h1><p>Manage bid decisions, capture posture, probability, value, deadlines, and execution actions in one workspace.</p></div><button className="secondary-button" onClick={load}><RefreshCw size={16}/> Refresh</button></header>
 <section className="workspace-summary"><div><span>Active pursuits</span><strong>{active.length}</strong><small>Excludes closed outcomes</small></div><div><span>Total value</span><strong>{money.format(totalValue)}</strong><small>Active estimated value</small></div><div><span>Weighted pipeline</span><strong>{money.format(weighted)}</strong><small>Value × win probability</small></div><div><span>Overdue</span><strong>{overdue}</strong><small>Past-due pursuit deadlines</small></div><div><span>Due within 14 days</span><strong>{dueSoon}</strong><small>Upcoming, excludes overdue</small></div></section>
 {error&&<div className="system-banner warning" role="alert">{error}</div>}<section className="data-panel"><div className="kanban-help">Drag cards between stages or use the stage selector. Changes appear after saving. Scroll horizontally to see closed outcomes.</div>{loading?<div className="table-state" role="status"><RefreshCw className="spin"/><strong>Loading pursuits…</strong></div>:!rows.length&&!error?<div className="table-state"><strong>No pursuits yet</strong><p>Create a pursuit from an opportunity in your pipeline.</p><Link className="secondary-button" href="/capture/pipelines">View pipeline</Link></div>:null}<div className="kanban-board">{pursuitStages.map(stage=><section className={`kanban-column ${dragStage===stage?"drag-over":""}`} key={stage} onDragOver={e=>{e.preventDefault();setDragStage(stage)}} onDragLeave={()=>setDragStage(current=>current===stage?"":current)} onDrop={e=>{e.preventDefault();const id=Number(e.dataTransfer.getData("text/pursuit-id")||dragging);if(id)void movePursuit(id,stage)}}><header><span>{human(stage)}</span><b>{rows.filter(r=>r.stage===stage).length}</b></header>{rows.filter(r=>r.stage===stage).map(r=><article className={`kanban-card pursuit-card ${dragging===r.id?"dragging":""}`} key={r.id} draggable onDragStart={e=>{setDragging(r.id);e.dataTransfer.effectAllowed="move";e.dataTransfer.setData("text/pursuit-id",String(r.id))}} onDragEnd={()=>{setDragging(null);setDragStage("")}} onClick={()=>setSelected(r)}><button type="button" className="pursuit-open" onClick={event=>{event.stopPropagation();setSelected(r)}} aria-label={`Open pursuit: ${r.title}`}><strong>{r.title}</strong></button><p>{r.next_action||"No next action set"}</p><div className="pursuit-card-metrics"><span>{money.format(Number(r.estimated_value??0))}</span><span>{r.probability_of_win}% Pwin</span></div>{r.due_date?<small>Due {new Date(r.due_date).toLocaleDateString()}</small>:null}<label onClick={e=>e.stopPropagation()}><span>Move to</span><select aria-label={`Stage: ${r.title}`} disabled={busy!==null} value={r.stage} onChange={e=>void movePursuit(r.id,e.target.value)}>{pursuitStages.map(s=><option key={s} value={s}>{human(s)}</option>)}</select></label></article>)}</section>)}</div></section>
 {selected&&<dialog ref={dialogRef} className="record-modal pursuit-detail-modal" aria-labelledby="pursuit-detail-title" onCancel={()=>setSelected(null)}><header><div><span className="eyebrow">Capture plan</span><h2 id="pursuit-detail-title">{selected.title}</h2></div><button type="button" className="icon-button" aria-label="Close pursuit" onClick={()=>setSelected(null)}>×</button></header>{error&&<p className="form-error" role="alert">{error}</p>}<fieldset className="record-form pursuit-fields" disabled={busy!==null}><label><span>Stage</span><select value={selected.stage} onChange={e=>void patch(selected.id,{stage:e.target.value})}>{["triage","qualify","bid_decision","capture","proposal","submitted","awarded","lost","no_bid","archived"].map(s=><option key={s} value={s}>{human(s)}</option>)}</select></label><label><span>Win probability</span><input type="number" min="0" max="100" value={selected.probability_of_win} onChange={e=>setSelected({...selected,probability_of_win:Number(e.target.value)})} onBlur={()=>void patch(selected.id,{probability_of_win:selected.probability_of_win})}/></label><label><span>Estimated value</span><input type="number" value={selected.estimated_value??""} onChange={e=>setSelected({...selected,estimated_value:e.target.value})} onBlur={()=>void patch(selected.id,{estimated_value:selected.estimated_value||null})}/></label><label><span>Due date</span><input type="datetime-local" value={localDateTime(selected.due_date)} onChange={e=>{void patch(selected.id,{due_date:e.target.value?new Date(e.target.value).toISOString():null})}}/></label><label><span>Incumbent</span><input value={selected.incumbent??""} onChange={e=>setSelected({...selected,incumbent:e.target.value})} onBlur={()=>void patch(selected.id,{incumbent:selected.incumbent})}/></label><label><span>Next action</span><textarea value={selected.next_action??""} onChange={e=>setSelected({...selected,next_action:e.target.value})} onBlur={()=>void patch(selected.id,{next_action:selected.next_action})}/></label></fieldset><footer><span className="capture-score">Weighted value: {money.format(Number(selected.estimated_value??0)*(selected.probability_of_win/100))}</span><button className="primary-button" onClick={()=>setSelected(null)} disabled={busy!==null}>Done</button></footer></dialog>}
 </>;
}

export function TasksWorkspace(){
 const [rows,setRows]=useState<Task[]>([]);
 const [title,setTitle]=useState("");
 const [due,setDue]=useState("");
 const [error,setError]=useState("");
 const [loading,setLoading]=useState(true);
 const [busy,setBusy]=useState(false);
 const load=useCallback(async()=>{
   setLoading(true);
   try { setRows(normalizeList(await apiGet<Task[]>("/tasks/?page_size=250")));setError(""); }
   catch(e) { setError(e instanceof Error?e.message:"Unable to load tasks"); }
   finally { setLoading(false); }
 },[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function mutate(action:()=>Promise<unknown>){
   if(busy)return;
   setBusy(true);setError("");
   try { await action();await load(); }
   catch(e) { setError(e instanceof Error?e.message:"Task could not be saved. Try again."); }
   finally { setBusy(false); }
 }
 async function create(event:FormEvent){
   event.preventDefault();
   if(!title.trim())return;
   await mutate(async()=>{
     await apiPost("/workflow/tasks/",{title:title.trim(),due_at:due?new Date(due).toISOString():null});
     setTitle("");setDue("");
   });
 }
 return <>
   <header className="module-header"><div><span className="eyebrow">Execution management</span><h1>Tasks</h1><p>Create, complete, and track capture work with due dates and pipeline relationships.</p></div><button className="secondary-button" disabled={loading||busy} onClick={()=>void load()}><RefreshCw size={16}/>Refresh</button></header>
   <section className="data-panel">
     <form className="quick-create-form" onSubmit={create}>
       <label><span>Task title</span><input value={title} onChange={e=>setTitle(e.target.value)} placeholder="Add a task…" required disabled={busy}/></label>
       <label><span>Due date (your local time)</span><input type="datetime-local" value={due} onChange={e=>setDue(e.target.value)} disabled={busy}/></label>
       <button className="primary-button" disabled={busy||!title.trim()}><Plus size={16}/>{busy?"Saving…":"Add task"}</button>
     </form>
     {error&&<div className="form-error" role="alert">{error}</div>}
     {loading?<div className="table-state compact-state" role="status"><RefreshCw className="spin"/><strong>Loading tasks…</strong></div>:!error&&!rows.length?<div className="table-state compact-state"><CheckCircle2/><strong>No tasks yet</strong><p>Add your next capture action above. Set a due date to keep it visible in your workspace deadlines.</p></div>:null}
     <div className="task-list">{rows.map(task=><article className={`task-row ${task.completed?"complete":""}`} key={task.id}>
       <button className="icon-button" aria-label={`${task.completed?"Mark incomplete":"Complete"}: ${task.title}`} aria-pressed={task.completed} disabled={busy||loading} onClick={()=>void mutate(()=>apiPatch(`/tasks/${task.id}/`,{completed:!task.completed}))}>{task.completed?<CheckCircle2/>:<Circle/>}</button>
       <div><strong>{task.title}</strong><span>{task.due_at?new Date(task.due_at).toLocaleString():"No due date"}</span></div>
       <button className="icon-button" aria-label={`Delete task: ${task.title}`} disabled={busy||loading} onClick={()=>void mutate(()=>apiDelete(`/tasks/${task.id}/`))}><Trash2 size={17}/></button>
     </article>)}</div>
   </section>
 </>;
}

export function SavedSearchesWorkspace(){
 const [rows,setRows]=useState<SavedSearch[]>([]);const [error,setError]=useState("");const [loading,setLoading]=useState(true);const [removing,setRemoving]=useState<number|null>(null);
 const load=useCallback(async()=>{setLoading(true);try{setRows(normalizeList(await apiGet<SavedSearch[]>("/saved-searches/?page_size=250")));setError("")}catch(e){setError(e instanceof Error?e.message:"Unable to load searches")}finally{setLoading(false)}},[]);
 useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);
 async function remove(id:number){setRemoving(id);setError("");try{await apiDelete(`/saved-searches/${id}/`);await load()}catch(e){setError(e instanceof Error?e.message:"Saved search could not be deleted. Try again.")}finally{setRemoving(null)}}
 return <>
   <header className="module-header"><div><span className="eyebrow">Opportunity monitoring</span><h1>Saved Searches</h1><p>Reuse live SAM.gov filters and maintain searches that feed future alerts.</p></div><button className="secondary-button" onClick={load} disabled={loading||removing!==null}><RefreshCw size={16}/> Refresh</button></header>
   {error&&<div className="system-banner warning" role="alert">{error}</div>}
   <section className="data-panel">
     {loading?<div className="table-state compact-state" role="status"><RefreshCw className="spin"/><strong>Loading saved searches…</strong></div>:!error&&!rows.length?<div className="table-state compact-state"><Save/><strong>No saved searches yet</strong><p>Save your filters from opportunity search to run them again and monitor new matches.</p><Link className="secondary-button" href="/opportunities/federal-contracts">Find opportunities</Link></div>:null}
     <div className="saved-search-grid">{rows.map(row=>{
       const {source,...searchFilters}=row.filters;
       const query=new URLSearchParams(searchFilters).toString();
       const route=source==="grants.gov"?"/opportunities/federal-grants":"/opportunities/federal-contracts";
       return <article className="saved-search-card" key={row.id}>
         <div><Save size={18}/><span>{row.alert_frequency}</span></div><h3>{row.name}</h3>
         <p>{Object.entries(row.filters).filter(([,value])=>value).map(([key,value])=>`${human(key)}: ${value}`).join(" · ")||"No filters"}</p>
         <footer><Link className="primary-button" href={`${route}?${query}`}>Run search</Link><button className="icon-button" aria-label={`Delete saved search: ${row.name}`} disabled={removing!==null||loading} onClick={()=>void remove(row.id)}><Trash2 size={17}/></button></footer>
       </article>;
     })}</div>
   </section>
 </>;
}
