"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import {
  BadgeDollarSign, BriefcaseBusiness, Calculator, CheckCircle2, CircleDollarSign,
  Layers3, LoaderCircle, Plus, RefreshCw, ShieldAlert, Trash2, TrendingUp,
} from "lucide-react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";

type Money = string | number;
type Plan = {
  id:number; name:string; revision:number; status:string;
  fringe_percent:Money; overhead_percent:Money; ga_percent:Money;
  material_handling_percent:Money; subcontract_handling_percent:Money;
  payroll_burden_percent:Money; target_profit_percent:Money;
  minimum_margin_percent:Money; annual_escalation_percent:Money;
  pursuit_cost:Money; notes:string; updated_at:string;
};
type Item = {
  id:number; category:string; name:string; clin_id?:number|null; clin?:string;
  quantity:Money; unit_cost:Money; labor_hours:Money; labor_rate:Money;
  option_year:number; escalation_percent:Money; source:string; source_kind:string;
  direct:Money; total_cost:Money;
};
type Clin = {id:number;clin:string;description:string;option_year:number;quantity:Money;unit:string;cost:Money;target_price:Money};
type Scenario = {id:number;scenario_type:string;profit_percent:Money;cost_adjustment_percent:Money;price_adjustment_percent:Money;cost:Money;price:Money;profit:Money;margin_percent:Money;notes:string};
type Guardrail = {severity:string;title:string;detail:string};
type PtwEvidence = {award_id:number;source_id:string;award_number:string;recipient_name:string;awarding_agency:string;naics_code:string;psc_code:string;raw_value:Money;adjusted_value:Money;start_date?:string|null;end_date?:string|null;match_score:number;source:string;source_url?:string};
type PtwViability = {price:Money|null;profit:Money|null;margin_percent:Money|null;clears_margin_floor:boolean};
type PriceToWin = {
  range:{competitive_floor:Money|null;target:Money|null;protective_ceiling:Money|null};
  confidence:number;evidence_count:number;strong_comparable_count:number;
  current_pricing:{price:Money|null;cost:Money;margin_percent:Money|null;minimum_margin_percent:Money|null;revision:number|null;status:string;position:string};
  viability:{competitive_floor:PtwViability;modeled_target:PtwViability;protective_ceiling:PtwViability};
  evidence:PtwEvidence[];assumptions:string[];warnings:string[];
  history:Array<{id:number;created_at:string;competitive_floor:Money|null;target_price:Money|null;protective_ceiling:Money|null;confidence:number;evidence_count:number}>;
  classification:string;recorded_snapshot_id?:number;
};
type Payload = {
  plan:Plan;
  totals:Record<string,Money>;
  items:Item[];
  clins:Clin[];
  scenarios:Scenario[];
  guardrails:Guardrail[];
  opportunity:{source_id:string;title:string;solicitation_number:string;agency:string};
};

const currency = (value:Money|undefined) => new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(value||0));
const pct = (value:Money|undefined) => `${Number(value||0).toFixed(1)}%`;
const categories = [
  ["labor","Labor"],["material","Materials"],["travel","Travel"],["equipment","Equipment"],
  ["subcontract","Subcontractor"],["bond","Bond"],["insurance","Insurance"],["other","Other Direct Cost"],
];

export function PricingWorkspace({noticeId}:{noticeId:string}) {
  const[data,setData]=useState<Payload|null>(null);
  const[busy,setBusy]=useState("");
  const[message,setMessage]=useState("");
  const[ptw,setPtw]=useState<PriceToWin|null>(null);
  const[section,setSection]=useState<"summary"|"costs"|"clins"|"scenarios"|"ptw"|"rates">("summary");
  const[item,setItem]=useState({category:"labor",name:"",quantity:"1",unit_cost:"",labor_hours:"",labor_rate:"",option_year:"0",clin_id:""});
  const[clin,setClin]=useState({clin:"",description:"",option_year:"0",quantity:"1",unit:"LOT"});

  const endpoint=`/pricing/opportunities/${encodeURIComponent(noticeId)}/`;
  const ptwEndpoint=`/pricing/opportunities/${encodeURIComponent(noticeId)}/price-to-win/`;

  const load=useCallback(async()=>{
    setBusy("load");
    try{
      const [pricing,priceToWin]=await Promise.all([
        apiGet<Payload>(endpoint),
        apiGet<PriceToWin>(ptwEndpoint).catch(()=>null),
      ]);
      setData(pricing);setPtw(priceToWin);setMessage("");
    }
    catch(error){setMessage(error instanceof Error?error.message:"Pricing workspace could not be loaded.")}
    finally{setBusy("")}
  },[endpoint,ptwEndpoint]);

  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);

  async function mutate(payload:Record<string,unknown>,statusKey="save"){
    setBusy(statusKey);setMessage("");
    try{const next=await apiPatch<Payload>(endpoint,payload);setData(next);return next}
    catch(error){setMessage(error instanceof Error?error.message:"Pricing change could not be saved.");return null}
    finally{setBusy("")}
  }

  async function refreshPtw(record=false){
    setBusy(record?"ptw-record":"ptw");setMessage("");
    try{
      const result=record?await apiPost<PriceToWin>(ptwEndpoint,{}):await apiGet<PriceToWin>(ptwEndpoint);
      setPtw(result);
      if(record)setMessage("Price-to-win snapshot recorded.");
    }catch(error){setMessage(error instanceof Error?error.message:"Price-to-win intelligence could not be refreshed.")}
    finally{setBusy("")}
  }

  async function addItem(event:FormEvent){
    event.preventDefault();
    if(!item.name.trim())return;
    const result=await mutate({
      action:"add_item",category:item.category,name:item.name,quantity:item.quantity||1,unit_cost:item.unit_cost||0,
      labor_hours:item.labor_hours||0,labor_rate:item.labor_rate||0,option_year:Number(item.option_year||0),
      clin_id:item.clin_id?Number(item.clin_id):null,
    },"add-item");
    if(result)setItem({...item,name:"",unit_cost:"",labor_hours:"",labor_rate:""});
  }

  async function addClin(event:FormEvent){
    event.preventDefault();
    if(!clin.clin.trim())return;
    const result=await mutate({action:"add_clin",...clin,option_year:Number(clin.option_year||0)},"add-clin");
    if(result)setClin({clin:"",description:"",option_year:"0",quantity:"1",unit:"LOT"});
  }

  const categoryTotals=useMemo(()=>{
    const rows:Record<string,number>={};
    data?.items.forEach(row=>{rows[row.category]=(rows[row.category]||0)+Number(row.total_cost||0)});
    return rows;
  },[data]);

  if(!data)return <section className="pricing-shell"><div className="pricing-loading"><LoaderCircle className="spin"/><strong>{busy?"Building pricing workspace…":"Pricing unavailable"}</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></div></section>;

  const t=data.totals;
  const marginOk=Number(t.margin_percent||0)>=Number(data.plan.minimum_margin_percent||0);

  return <section className="pricing-shell">
    <header className="pricing-hero">
      <div><span className="eyebrow">V3.0 PRICING & ECONOMICS</span><h2>Pricing Workspace</h2><p>Build auditable delivery cost, indirects, profit, CLIN pricing, and bid scenarios. ForgeGov calculates the math; AI can explain it later.</p></div>
      <div className="pricing-hero-actions">
        <span className={`pricing-status ${data.plan.status}`}>{data.plan.status.replaceAll("_"," ")}</span>
        <span>Revision {data.plan.revision}</span>
        <button className="secondary-button" onClick={()=>void load()} disabled={busy==="load"}><RefreshCw size={15}/> Refresh</button>
      </div>
    </header>

    {message&&<div className="system-banner warning">{message}</div>}

    <div className="pricing-kpis">
      <article><span>Target Price</span><strong>{currency(t.price)}</strong><small>Total evaluated target</small></article>
      <article><span>Delivery Cost</span><strong>{currency(t.total_cost)}</strong><small>Direct + indirect cost</small></article>
      <article className={marginOk?"healthy":"risk"}><span>Projected Profit</span><strong>{currency(t.profit)}</strong><small>{pct(t.margin_percent)} margin · {pct(t.markup_percent)} markup</small></article>
      <article><span>Pursuit Cost</span><strong>{currency(t.pursuit_cost)}</strong><small>Pre-award investment</small></article>
    </div>

    <nav className="pricing-subnav">
      <button className={section==="summary"?"active":""} onClick={()=>setSection("summary")}><Calculator size={15}/> Summary</button>
      <button className={section==="costs"?"active":""} onClick={()=>setSection("costs")}><BriefcaseBusiness size={15}/> Cost Build-Up</button>
      <button className={section==="clins"?"active":""} onClick={()=>setSection("clins")}><Layers3 size={15}/> CLINs</button>
      <button className={section==="scenarios"?"active":""} onClick={()=>setSection("scenarios")}><TrendingUp size={15}/> Scenarios</button>
      <button className={section==="ptw"?"active":""} onClick={()=>setSection("ptw")}><BadgeDollarSign size={15}/> Price-to-Win <span className="tab-new-badge">M2</span></button>
      <button className={section==="rates"?"active":""} onClick={()=>setSection("rates")}><CircleDollarSign size={15}/> Indirect Rates</button>
    </nav>

    {section==="summary"&&<>
      <div className="pricing-summary-grid">
        <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">COST STRUCTURE</span><h3>Where the money goes</h3></div></div>
          <div className="pricing-cost-breakdown">
            {categories.map(([key,label])=><div key={key}><span>{label}</span><strong>{currency(categoryTotals[key]||0)}</strong></div>)}
            <div><span>Fringe</span><strong>{currency(t.fringe)}</strong></div>
            <div><span>Payroll burden</span><strong>{currency(t.payroll_burden)}</strong></div>
            <div><span>Overhead</span><strong>{currency(t.overhead)}</strong></div>
            <div><span>G&A</span><strong>{currency(t.ga)}</strong></div>
          </div>
        </section>
        <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">ECONOMIC GUARDRAILS</span><h3>What needs attention</h3></div></div>
          <div className="pricing-guardrails">{data.guardrails.map((row,index)=><article className={row.severity} key={`${row.title}-${index}`}>{row.severity==="success"?<CheckCircle2/>:<ShieldAlert/>}<div><strong>{row.title}</strong><p>{row.detail}</p></div></article>)}</div>
        </section>
      </div>
      <section className="data-panel pricing-scenario-strip"><div className="panel-title-row"><div><span className="eyebrow">SCENARIO RANGE</span><h3>Competitive → Target → Protective</h3></div></div>
        <div className="pricing-scenario-cards">{data.scenarios.map(row=><article key={row.id}><span>{row.scenario_type}</span><strong>{currency(row.price)}</strong><b>{pct(row.margin_percent)} margin</b><small>{currency(row.profit)} profit</small></article>)}</div>
      </section>
    </>}

    {section==="costs"&&<div className="pricing-work-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">ADD COST</span><h3>Cost Build-Up</h3></div></div>
        <form className="pricing-form" onSubmit={addItem}>
          <label>Category<select value={item.category} onChange={e=>setItem({...item,category:e.target.value})}>{categories.map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label>
          <label className="wide">Name<input value={item.name} onChange={e=>setItem({...item,name:e.target.value})} placeholder={item.category==="labor"?"Senior Technician":"Cost item description"}/></label>
          {item.category==="labor"?<>
            <label>Hours<input type="number" step="0.01" value={item.labor_hours} onChange={e=>setItem({...item,labor_hours:e.target.value})}/></label>
            <label>Hourly Cost<input type="number" step="0.01" value={item.labor_rate} onChange={e=>setItem({...item,labor_rate:e.target.value})}/></label>
          </>:<>
            <label>Quantity<input type="number" step="0.001" value={item.quantity} onChange={e=>setItem({...item,quantity:e.target.value})}/></label>
            <label>Unit Cost<input type="number" step="0.01" value={item.unit_cost} onChange={e=>setItem({...item,unit_cost:e.target.value})}/></label>
          </>}
          <label>Option Year<input type="number" min="0" value={item.option_year} onChange={e=>setItem({...item,option_year:e.target.value})}/></label>
          <label>CLIN<select value={item.clin_id} onChange={e=>setItem({...item,clin_id:e.target.value})}><option value="">Unassigned</option>{data.clins.map(row=><option key={row.id} value={row.id}>{row.clin}</option>)}</select></label>
          <button className="primary-button wide" disabled={busy==="add-item"}><Plus size={16}/>{busy==="add-item"?"Adding…":"Add Cost Item"}</button>
        </form>
      </section>
      <section className="data-panel pricing-item-panel"><div className="panel-title-row"><div><span className="eyebrow">MODEL</span><h3>{data.items.length} cost items</h3></div></div>
        <div className="pricing-item-list">{data.items.length?data.items.map(row=><article key={row.id}><span className={`pricing-cat ${row.category}`}>{row.category}</span><div><strong>{row.name}</strong><small>{row.category==="labor"?`${Number(row.labor_hours).toLocaleString()} hrs × ${currency(row.labor_rate)}`:`${Number(row.quantity).toLocaleString()} × ${currency(row.unit_cost)}`} {row.clin?`· ${row.clin}`:""} {row.option_year?`· OY${row.option_year}`:""}</small></div><div className="pricing-row-money"><b>{currency(row.total_cost)}</b><small>burdened cost</small></div><button className="icon-button danger-button" onClick={()=>void mutate({action:"delete_item",id:row.id},"delete")}><Trash2 size={15}/></button></article>):<div className="table-state compact-state"><Calculator/><strong>No costs entered yet</strong><p>Add labor, materials, travel, equipment, or subcontractor costs.</p></div>}</div>
      </section>
    </div>}

    {section==="clins"&&<div className="pricing-work-grid">
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">PRICE STRUCTURE</span><h3>Add CLIN</h3></div></div>
        <form className="pricing-form" onSubmit={addClin}>
          <label>CLIN<input value={clin.clin} onChange={e=>setClin({...clin,clin:e.target.value})} placeholder="0001"/></label>
          <label className="wide">Description<input value={clin.description} onChange={e=>setClin({...clin,description:e.target.value})} placeholder="Base maintenance services"/></label>
          <label>Option Year<input type="number" min="0" value={clin.option_year} onChange={e=>setClin({...clin,option_year:e.target.value})}/></label>
          <label>Quantity<input type="number" step="0.001" value={clin.quantity} onChange={e=>setClin({...clin,quantity:e.target.value})}/></label>
          <label>Unit<input value={clin.unit} onChange={e=>setClin({...clin,unit:e.target.value})}/></label>
          <button className="primary-button wide" disabled={busy==="add-clin"}><Plus size={16}/> Add CLIN</button>
        </form>
      </section>
      <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">CLIN SUMMARY</span><h3>Evaluated price structure</h3></div></div>
        <div className="pricing-clin-list">{data.clins.length?data.clins.map(row=><article key={row.id}><div><strong>{row.clin}</strong><span>{row.description||"No description"} · {row.option_year?`Option Year ${row.option_year}`:"Base"}</span></div><div><small>Cost</small><b>{currency(row.cost)}</b></div><div><small>Target Price</small><strong>{currency(row.target_price)}</strong></div><button className="icon-button danger-button" onClick={()=>void mutate({action:"delete_clin",id:row.id},"delete-clin")}><Trash2 size={15}/></button></article>):<div className="table-state compact-state"><Layers3/><strong>No CLINs configured</strong></div>}</div>
      </section>
    </div>}

    {section==="scenarios"&&<section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">BID SCENARIOS</span><h3>Stress-test the economics</h3></div></div>
      <div className="pricing-scenario-editor">{data.scenarios.map(row=><article key={row.id}><header><span>{row.scenario_type}</span><strong>{currency(row.price)}</strong></header><div><label>Profit / Markup %<input type="number" step="0.1" defaultValue={Number(row.profit_percent)} onBlur={e=>void mutate({action:"update_scenario",id:row.id,profit_percent:e.target.value},"scenario")}/></label><label>Cost Adjustment %<input type="number" step="0.1" defaultValue={Number(row.cost_adjustment_percent)} onBlur={e=>void mutate({action:"update_scenario",id:row.id,cost_adjustment_percent:e.target.value},"scenario")}/></label><label>Price Adjustment %<input type="number" step="0.1" defaultValue={Number(row.price_adjustment_percent)} onBlur={e=>void mutate({action:"update_scenario",id:row.id,price_adjustment_percent:e.target.value},"scenario")}/></label></div><footer><span>{currency(row.cost)} cost</span><b>{currency(row.profit)} profit</b><strong>{pct(row.margin_percent)} margin</strong></footer></article>)}</div>
    </section>}

    {section==="ptw"&&<section className="ptw-workspace">
      <header className="ptw-header data-panel">
        <div><span className="eyebrow">M2 COMPETITIVE PRICING</span><h3>Price-to-Win Intelligence</h3><p>ForgeGov models a competitive range from public historical awards and compares it against your actual delivery economics. This is decision support—not a prediction of a competitor&apos;s confidential bid.</p></div>
        <div className="ptw-actions"><button className="secondary-button" onClick={()=>void refreshPtw(false)} disabled={busy==="ptw"}><RefreshCw size={15}/> Refresh evidence</button><button className="primary-button" onClick={()=>void refreshPtw(true)} disabled={busy==="ptw-record"}>Record snapshot</button></div>
      </header>
      {!ptw?<div className="data-panel table-state"><TrendingUp/><strong>No comparable award model available yet</strong><p>Sync USAspending award history or broaden the opportunity classification evidence.</p></div>:<>
        <div className="ptw-range-grid">
          <article><span>Competitive Floor</span><strong>{ptw.range.competitive_floor==null?"Insufficient evidence":currency(ptw.range.competitive_floor)}</strong><small>{ptw.viability.competitive_floor.margin_percent==null?"Margin unavailable":`${pct(ptw.viability.competitive_floor.margin_percent)} margin`}</small><b className={ptw.viability.competitive_floor.clears_margin_floor?"viable":"not-viable"}>{ptw.viability.competitive_floor.clears_margin_floor?"Economically viable":"Below margin floor"}</b></article>
          <article className="target"><span>Modeled Target</span><strong>{ptw.range.target==null?"Insufficient evidence":currency(ptw.range.target)}</strong><small>{ptw.viability.modeled_target.margin_percent==null?"Margin unavailable":`${pct(ptw.viability.modeled_target.margin_percent)} margin · ${currency(ptw.viability.modeled_target.profit||0)} profit`}</small><b className={ptw.viability.modeled_target.clears_margin_floor?"viable":"not-viable"}>{ptw.viability.modeled_target.clears_margin_floor?"Clears margin floor":"Financially unattractive"}</b></article>
          <article><span>Protective Ceiling</span><strong>{ptw.range.protective_ceiling==null?"Insufficient evidence":currency(ptw.range.protective_ceiling)}</strong><small>{ptw.viability.protective_ceiling.margin_percent==null?"Margin unavailable":`${pct(ptw.viability.protective_ceiling.margin_percent)} margin`}</small><b className={ptw.viability.protective_ceiling.clears_margin_floor?"viable":"not-viable"}>{ptw.viability.protective_ceiling.clears_margin_floor?"Economically viable":"Below margin floor"}</b></article>
        </div>

        <div className="ptw-intel-grid">
          <section className="data-panel">
            <div className="panel-title-row"><div><span className="eyebrow">POSITION</span><h3>Your price vs modeled market</h3></div><span className={`ptw-confidence ${ptw.confidence>=70?"high":ptw.confidence>=45?"medium":"low"}`}>{ptw.confidence}% confidence</span></div>
            <div className="ptw-position">
              <div><span>Current target bid</span><strong>{ptw.current_pricing.price==null?"Not priced":currency(ptw.current_pricing.price)}</strong></div>
              <div><span>Delivery cost</span><strong>{currency(ptw.current_pricing.cost)}</strong></div>
              <div><span>Configured margin floor</span><strong>{ptw.current_pricing.minimum_margin_percent==null?"—":pct(ptw.current_pricing.minimum_margin_percent)}</strong></div>
              <div><span>Market position</span><strong className={`position-${ptw.current_pricing.position}`}>{ptw.current_pricing.position.replaceAll("_"," ")}</strong></div>
            </div>
            <div className="ptw-evidence-summary"><b>{ptw.evidence_count}</b><span>modeled comparable awards</span><b>{ptw.strong_comparable_count}</b><span>high-strength matches</span></div>
          </section>

          <section className="data-panel">
            <div className="panel-title-row"><div><span className="eyebrow">MODEL WARNINGS</span><h3>What could invalidate the range</h3></div></div>
            <div className="pricing-guardrails">{ptw.warnings.length?ptw.warnings.map((warning,index)=><article className="warning" key={index}><ShieldAlert/><div><strong>Pricing evidence caution</strong><p>{warning}</p></div></article>):<article className="success"><CheckCircle2/><div><strong>Evidence is usable</strong><p>No major price-to-win evidence warnings were detected.</p></div></article>}</div>
            <details className="ptw-assumptions"><summary>Model assumptions ({ptw.assumptions.length})</summary>{ptw.assumptions.map((row,index)=><p key={index}>{row}</p>)}</details>
          </section>
        </div>

        <section className="data-panel">
          <div className="panel-title-row"><div><span className="eyebrow">OFFICIAL HISTORICAL EVIDENCE</span><h3>Comparable federal awards</h3></div><small>{ptw.classification.replaceAll("_"," ")}</small></div>
          <div className="ptw-evidence-table">{ptw.evidence.length?ptw.evidence.map(row=><article key={row.award_id}><div><strong>{row.recipient_name||"Unknown recipient"}</strong><span>{row.award_number||row.source_id} · {row.awarding_agency||"Agency unavailable"}</span><small>{row.naics_code?`NAICS ${row.naics_code}`:""} {row.psc_code?`· PSC ${row.psc_code}`:""}</small></div><div><span>Historical value</span><b>{currency(row.raw_value)}</b></div><div><span>Normalized value</span><strong>{currency(row.adjusted_value)}</strong></div><div><span>Match</span><strong>{row.match_score}/100</strong></div>{row.source_url?<a href={row.source_url} target="_blank" rel="noreferrer">Source ↗</a>:<span/>}</article>):<div className="table-state compact-state"><BadgeDollarSign/><strong>No comparable awards stored</strong><p>Run USAspending ingestion for this agency/NAICS/PSC to strengthen the model.</p></div>}</div>
        </section>

        {ptw.history.length>0&&<section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">DECISION HISTORY</span><h3>Recorded price-to-win snapshots</h3></div></div><div className="ptw-history">{ptw.history.map(row=><article key={row.id}><time>{new Date(row.created_at).toLocaleString()}</time><span>{row.confidence}% confidence · {row.evidence_count} comparables</span><strong>{row.target_price==null?"No target":currency(row.target_price)}</strong></article>)}</div></section>}
      </>}
    </section>}

    {section==="rates"&&<section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">INDIRECT RATE MODEL</span><h3>Opportunity-specific rates</h3></div></div>
      <div className="pricing-rate-grid">
        {[
          ["payroll_burden_percent","Payroll Burden"],["fringe_percent","Fringe"],["overhead_percent","Overhead"],["ga_percent","G&A"],
          ["material_handling_percent","Material Handling"],["subcontract_handling_percent","Sub Handling"],
          ["target_profit_percent","Target Profit / Markup"],["minimum_margin_percent","Minimum Margin"],["annual_escalation_percent","Annual Escalation"],
        ].map(([key,label])=><label key={key}><span>{label}</span><div><input type="number" step="0.1" defaultValue={Number(data.plan[key as keyof Plan]||0)} onBlur={e=>void mutate({action:"update_plan",[key]:e.target.value},"rates")}/><b>%</b></div></label>)}
        <label><span>Pursuit Cost</span><div><b>$</b><input type="number" step="100" defaultValue={Number(data.plan.pursuit_cost||0)} onBlur={e=>void mutate({action:"update_plan",pursuit_cost:e.target.value},"rates")}/></div></label>
      </div>
      <div className="pricing-approval-bar"><div><strong>Pricing Revision {data.plan.revision}</strong><span>Changes are persisted and feed Pursuit Decision Intelligence.</span></div><select value={data.plan.status} onChange={e=>void mutate({action:"update_plan",status:e.target.value},"status")}><option value="draft">Draft</option><option value="review">Ready for Review</option><option value="approved">Approved</option><option value="locked">Locked</option></select><button className="secondary-button" onClick={()=>void mutate({action:"new_revision"},"revision")}>Create New Revision</button></div>
    </section>}
  </section>;
}
