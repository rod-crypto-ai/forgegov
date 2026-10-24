"use client";
import Image from "next/image";
import { useRef, useState } from "react";
import { Maximize2, X } from "lucide-react";
import styles from "./public-landing.module.css";
const views = [
  {key:"discovery",label:"Discover",title:"Search the work. Check the source.",description:"Filter synchronized opportunities by keyword, agency, NAICS, and PSC. Inspect posted dates, deadlines, official-source links, and the recorded sync state."},
  {key:"market",label:"Qualify",title:"Put the buyer and award history in context.",description:"Research agencies, competitors, market categories, and contract vehicles using stored award evidence. Historical obligations do not guarantee future work."},
  {key:"capture",label:"Capture",title:"Keep ownership and next actions visible.",description:"Review pursuit stages, pipeline values, decision signals, and workload together. Values shown here belong to the demonstration workspace."},
  {key:"rooms",label:"Project Rooms",title:"A shared pursuit, with defined boundaries.",description:"Connect partner companies to the room and set permissions for uploads, comments, pricing, sensitive documents, exports, and access expiration."},
  {key:"forgeai",label:"ForgeAI",title:"Research assistance with human review.",description:"Select opportunity, capture, proposal, or market research. The interface shows available context and provider status. Generated responses require configured AI credentials; this tour does not simulate an AI answer."},
];
export function ProductTour() {
  const [active,setActive]=useState(2);
  const buttons=useRef<(HTMLButtonElement|null)[]>([]);
  const dialog=useRef<HTMLDialogElement>(null);
  const view=views[active];
  return <div className={styles.productTour}>
    <div className={styles.tourTabs} role="tablist" aria-label="ForgeGov product tour">{views.map((v,i)=><button type="button" key={v.key} ref={node=>{buttons.current[i]=node;}} role="tab" id={`tour-tab-${i}`} aria-controls="tour-panel" aria-selected={active===i} tabIndex={active===i?0:-1} onClick={()=>setActive(i)} onKeyDown={e=>{const next=e.key==="ArrowRight"?(i+1)%views.length:e.key==="ArrowLeft"?(i+views.length-1)%views.length:e.key==="Home"?0:e.key==="End"?views.length-1:null;if(next!==null){e.preventDefault();setActive(next);buttons.current[next]?.focus();}}}>{v.label}</button>)}</div>
    <div role="tabpanel" id="tour-panel" aria-labelledby={`tour-tab-${active}`} tabIndex={0} className={styles.tourPanel}>
      <div className={styles.tourBar}><span><i/> ACTUAL FORGEGOV INTERFACE</span><button type="button" onClick={()=>dialog.current?.showModal()}><Maximize2 size={15}/> Enlarge screenshot</button></div>
      <Image src={`/product/${view.key}.webp`} alt={`${view.title} Actual ForgeGov interface showing demonstration records.`} width={1440} height={900} sizes="(max-width: 768px) 100vw, 1200px" priority={active===2} className={styles.tourImage}/>
      <div className={styles.tourCaption}><div><strong>{view.title}</strong><p>{view.description}</p></div><span>Demonstration workspace<br/>Sample records · Not live listings</span></div>
    </div>
    <dialog ref={dialog} className={styles.imageDialog} onClick={e=>{if(e.target===e.currentTarget)dialog.current?.close();}}><button type="button" autoFocus onClick={()=>dialog.current?.close()} aria-label="Close enlarged screenshot"><X size={20}/> Close</button><Image src={`/product/${view.key}.webp`} alt={view.title} width={1440} height={900} sizes="100vw"/><p>Actual application interface · Demonstration records · Not live listings</p></dialog>
  </div>;
}
