"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle, BadgeDollarSign, BarChart3, BriefcaseBusiness, CircleDollarSign,
  LoaderCircle, RefreshCw, ShieldCheck, TrendingUp, WalletCards
} from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";

type Money = string|number;
type Portfolio = {
  summary:{
    pipeline_value:Money;weighted_pipeline_value:Money;modeled_revenue:Money;modeled_cost:Money;
    projected_profit:Money;weighted_profit:Money;portfolio_margin_percent:Money;weighted_margin_percent:Money;
    backlog_value:Money;option_year_value:Money;recommended_working_capital:Money;working_capital_gap:Money;
    active_opportunity_count:number;priced_opportunity_count:number;
  };
  opportunities:Array<{
    pipeline_id:number;source_id:string;title:string;agency:string;stage:string;probability_of_win:number;
    value:Money;weighted_value:Money;modeled_cost:Money|null;projected_profit:Money|null;margin_percent:Money|null;
    pricing_revision:number|null;pricing_status:string;working_capital_required:Money|null;working_capital_gap:Money|null;
    working_capital_risk:string;
  }>;
  agency_concentration:Array<{agency:string;pipeline_value:Money;weighted_value:Money;opportunity_count:number;share_percent:Money}>;
  stage_distribution:Array<{stage:string;value:Money;weighted_value:Money;count:number}>;
  working_capital_risk:Record<string,number>;
  risks:Array<{severity:string;title:string;detail:string}>;
  history:Array<{id:number;created_at:string;pipeline_value:Money;weighted_pipeline_value:Money;modeled_revenue:Money;projected_profit:Money;backlog_value:Money;portfolio_margin_percent:Money;working_capital_gap:Money}>;
};

const money=(v:Money|undefined|null)=>new Intl.NumberFormat("en-US",{style:"currency",currency:"USD",maximumFractionDigits:0}).format(Number(v||0));
const pct=(v:Money|undefined|null)=>`${Number(v||0).toFixed(1)}%`;

export default function ExecutivePortfolioPage(){
  const[data,setData]=useState<Portfolio|null>(null);
  const[busy,setBusy]=useState("");
  const[message,setMessage]=useState("");

  const load=useCallback(async()=>{
    setBusy("load");
    try{setData(await apiGet<Portfolio>("/reports/portfolio-intelligence/"));setMessage("")}
    catch(error){setMessage(error instanceof Error?error.message:"Portfolio intelligence could not be loaded.")}
    finally{setBusy("")}
  },[]);

  useEffect(()=>{const timer=window.setTimeout(()=>void load(),0);return()=>window.clearTimeout(timer)},[load]);

  async function snapshot(){
    setBusy("snapshot");setMessage("");
    try{
      const result=await apiPost<Portfolio>("/reports/portfolio-intelligence/",{});
      setData(result);setMessage("Executive portfolio snapshot recorded.");
    }catch(error){setMessage(error instanceof Error?error.message:"Portfolio snapshot could not be recorded.")}
    finally{setBusy("")}
  }

  const concentrationMax=useMemo(()=>Math.max(1,...(data?.agency_concentration.map(row=>Number(row.share_percent||0))??[1])),[data]);

  if(!data)return <main className="page-shell portfolio-page"><div className="table-state"><LoaderCircle className="spin"/><strong>{busy?"Building portfolio intelligence…":"Portfolio intelligence unavailable"}</strong><p>{message}</p><button className="secondary-button" onClick={()=>void load()}>Retry</button></div></main>;

  const s=data.summary;
  const pricedCoverage=s.active_opportunity_count?Math.round(s.priced_opportunity_count/s.active_opportunity_count*100):0;

  return <main className="page-shell portfolio-page">
    <header className="portfolio-hero">
      <div><span className="eyebrow">FORGEGOV V3.0 — EXECUTIVE FINANCIAL INTELLIGENCE</span><h1>Portfolio Revenue & Profit Intelligence</h1><p>See what the pipeline is worth, what it is likely to produce, what margin it carries, and whether the company has enough working capital to execute the work it is pursuing.</p></div>
      <div className="portfolio-actions"><button className="secondary-button" onClick={()=>void load()} disabled={busy==="load"}><RefreshCw size={16}/> Refresh</button><button className="primary-button" onClick={()=>void snapshot()} disabled={busy==="snapshot"}>{busy==="snapshot"?"Recording…":"Record Executive Snapshot"}</button></div>
    </header>

    {message&&<div className="system-banner">{message}</div>}

    <section className="portfolio-kpis">
      <article><BadgeDollarSign/><div><span>Active Pipeline</span><strong>{money(s.pipeline_value)}</strong><small>{s.active_opportunity_count} active pursuits</small></div></article>
      <article><TrendingUp/><div><span>Weighted Pipeline</span><strong>{money(s.weighted_pipeline_value)}</strong><small>Probability-adjusted value</small></div></article>
      <article><CircleDollarSign/><div><span>Projected Profit</span><strong>{money(s.projected_profit)}</strong><small>{pct(s.portfolio_margin_percent)} modeled margin</small></div></article>
      <article><BriefcaseBusiness/><div><span>Backlog</span><strong>{money(s.backlog_value)}</strong><small>Awarded closeout value</small></div></article>
      <article className={Number(s.working_capital_gap)>0?"risk":""}><WalletCards/><div><span>Working Capital Gap</span><strong>{money(s.working_capital_gap)}</strong><small>{money(s.recommended_working_capital)} modeled requirement</small></div></article>
      <article><BarChart3/><div><span>Pricing Coverage</span><strong>{pricedCoverage}%</strong><small>{s.priced_opportunity_count}/{s.active_opportunity_count} pursuits priced</small></div></article>
    </section>

    <section className="portfolio-grid">
      <article className="data-panel">
        <div className="panel-title-row"><div><span className="eyebrow">EXECUTIVE RISK</span><h2>Portfolio guardrails</h2></div></div>
        <div className="portfolio-risk-list">{data.risks.map((row,index)=><div className={`portfolio-risk ${row.severity}`} key={`${row.title}-${index}`}>{row.severity==="success"?<ShieldCheck/>:<AlertTriangle/>}<div><strong>{row.title}</strong><p>{row.detail}</p></div></div>)}</div>
      </article>

      <article className="data-panel">
        <div className="panel-title-row"><div><span className="eyebrow">REVENUE QUALITY</span><h2>Modeled economics</h2></div></div>
        <div className="portfolio-econ-list">
          <div><span>Modeled Revenue</span><strong>{money(s.modeled_revenue)}</strong></div>
          <div><span>Modeled Cost</span><strong>{money(s.modeled_cost)}</strong></div>
          <div><span>Projected Profit</span><strong>{money(s.projected_profit)}</strong></div>
          <div><span>Weighted Profit</span><strong>{money(s.weighted_profit)}</strong></div>
          <div><span>Portfolio Margin</span><strong>{pct(s.portfolio_margin_percent)}</strong></div>
          <div><span>Option-Year Exposure</span><strong>{money(s.option_year_value)}</strong></div>
        </div>
      </article>
    </section>

    <section className="portfolio-grid">
      <article className="data-panel">
        <div className="panel-title-row"><div><span className="eyebrow">CUSTOMER CONCENTRATION</span><h2>Agency exposure</h2></div></div>
        <div className="agency-concentration-list">{data.agency_concentration.length?data.agency_concentration.map(row=><div key={row.agency}><div><strong>{row.agency}</strong><span>{row.opportunity_count} pursuit{row.opportunity_count===1?"":"s"} · {money(row.pipeline_value)}</span></div><div className="concentration-bar"><i style={{width:`${Math.min(100,Number(row.share_percent)/concentrationMax*100)}%`}}/></div><b>{pct(row.share_percent)}</b></div>):<div className="table-state compact-state"><BarChart3/><strong>No active agency concentration yet</strong></div>}</div>
      </article>

      <article className="data-panel">
        <div className="panel-title-row"><div><span className="eyebrow">PIPELINE MIX</span><h2>Stage-weighted exposure</h2></div></div>
        <div className="stage-distribution-list">{data.stage_distribution.map(row=><div key={row.stage}><span>{row.stage.replaceAll("_"," ")}</span><strong>{money(row.weighted_value)}</strong><small>{row.count} pursuit{row.count===1?"":"s"} · {money(row.value)} gross</small></div>)}</div>
      </article>
    </section>

    <section className="data-panel">
      <div className="panel-title-row"><div><span className="eyebrow">ACTIVE PORTFOLIO</span><h2>Revenue, margin & liquidity by pursuit</h2></div></div>
      <div className="portfolio-table-wrap"><table className="portfolio-table"><thead><tr><th>Opportunity</th><th>Stage</th><th>Gross Value</th><th>Weighted</th><th>Profit</th><th>Margin</th><th>Working Capital</th><th>Liquidity Risk</th></tr></thead><tbody>{data.opportunities.map(row=><tr key={row.pipeline_id}><td><Link href={`/opportunities/federal-contracts/${encodeURIComponent(row.source_id)}`}>{row.title}</Link><small>{row.agency}</small></td><td>{row.stage.replaceAll("_"," ")}</td><td>{money(row.value)}</td><td>{money(row.weighted_value)}</td><td>{row.projected_profit==null?"Not priced":money(row.projected_profit)}</td><td>{row.margin_percent==null?"—":pct(row.margin_percent)}</td><td>{row.working_capital_required==null?"Not modeled":money(row.working_capital_required)}</td><td><span className={`portfolio-risk-pill ${row.working_capital_risk}`}>{row.working_capital_risk.replaceAll("_"," ")}</span></td></tr>)}</tbody></table>{data.opportunities.length===0&&<div className="table-state compact-state"><BriefcaseBusiness/><strong>No active pursuits</strong><p>Add qualified opportunities to the pipeline to build the portfolio forecast.</p></div>}</div>
    </section>

    {data.history.length>0&&<section className="data-panel">
      <div className="panel-title-row"><div><span className="eyebrow">EXECUTIVE HISTORY</span><h2>Recorded portfolio snapshots</h2></div></div>
      <div className="portfolio-history">{data.history.map(row=><article key={row.id}><time>{new Date(row.created_at).toLocaleString()}</time><div><span>Weighted Pipeline</span><strong>{money(row.weighted_pipeline_value)}</strong></div><div><span>Profit</span><strong>{money(row.projected_profit)}</strong></div><div><span>Margin</span><strong>{pct(row.portfolio_margin_percent)}</strong></div><div><span>Capital Gap</span><strong>{money(row.working_capital_gap)}</strong></div></article>)}</div>
    </section>}
  </main>;
}
