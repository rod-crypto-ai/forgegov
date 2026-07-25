"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight, Award, BellRing, Building2, CalendarClock, ChevronRight,
  CircleDollarSign, Database, FileSearch, Handshake, Radar, Search,
  ShieldCheck, Sparkles, Target, TrendingUp, Users,
} from "lucide-react";
import { apiGet } from "@/lib/api";

type Summary = { opportunities?: { total?: number; active?: number }; awards?: { total?: number; obligated_total?: number }; pipeline?: { total?: number; by_stage?: Record<string, number>; weighted_value?: number }; pursuits?: { total?: number }; tasks?: { open?: number; overdue?: number }; contacts?: number; vendors?: number; agencies?: number; saved_searches?: number; };
type Integrations = { sam_gov?: { configured?: boolean }; usaspending?: { reachable?: boolean; stored_awards?: number } };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });

export default function DashboardPage() {
  const [summary, setSummary] = useState<Summary>({});
  const [integrations, setIntegrations] = useState<Integrations>({});
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([apiGet<Summary>("/dashboard/summary/"), apiGet<Integrations>("/integrations/status/?probe=true")]).then(([a,b]) => {setSummary(a); setIntegrations(b);}).catch((e) => setError(e instanceof Error ? e.message : "Backend unavailable")); }, []);
  const stages = useMemo(() => Object.entries(summary.pipeline?.by_stage ?? {}), [summary]);
  const total = Math.max(summary.pipeline?.total ?? 0, 1);

  return <div className="executive-dashboard">
    <section className="executive-head">
      <div>
        <span className="page-kicker">CAPTURE COMMAND CENTER</span>
        <h1>Good evening, Rod.</h1>
        <p>Find the right work, understand the market, and move every pursuit forward from one operating picture.</p>
      </div>
      <div className="head-actions"><Link href="/assistant" className="button ghost"><Sparkles size={17}/> Ask ForgeGov AI</Link><Link href="/opportunities/federal-contracts" className="button solid"><Search size={17}/> Find opportunities</Link></div>
    </section>

    {error && <div className="alert-strip"><ShieldCheck size={18}/><div><b>ForgeGov is running, but the API did not respond.</b><span>{error}</span></div></div>}

    <section className="data-status-strip">
      <div><i className={integrations.sam_gov?.configured ? "ok" : "warn"}/><span><b>SAM.gov</b><small>{integrations.sam_gov?.configured ? "Live search ready" : "API key required"}</small></span></div>
      <div><i className={integrations.usaspending?.reachable ? "ok" : "warn"}/><span><b>USAspending</b><small>{integrations.usaspending?.reachable ? "Live award data" : "Connection unavailable"}</small></span></div>
      <div><Database size={17}/><span><b>{integrations.usaspending?.stored_awards ?? summary.awards?.total ?? 0} awards indexed</b><small>Stored in ForgeGov</small></span></div>
      <Link href="/settings">Manage data sources <ChevronRight size={15}/></Link>
    </section>

    <section className="metric-grid">
      <Link href="/opportunities/federal-contracts" className="metric-card blue"><span><FileSearch/>Active opportunities</span><strong>{summary.opportunities?.active ?? 0}</strong><small>{summary.opportunities?.total ?? 0} notices indexed</small><i><TrendingUp size={14}/> Live market</i></Link>
      <Link href="/awards/federal-contracts" className="metric-card teal"><span><CircleDollarSign/>Award obligations</span><strong>{money.format(summary.awards?.obligated_total ?? 0)}</strong><small>{summary.awards?.total ?? 0} award records</small><i><Radar size={14}/> USAspending</i></Link>
      <Link href="/capture/pursuits" className="metric-card violet"><span><Target/>Active pursuits</span><strong>{summary.pursuits?.total ?? summary.pipeline?.total ?? 0}</strong><small>{money.format(summary.pipeline?.weighted_value ?? 0)} weighted pipeline</small><i><TrendingUp size={14}/> Capture</i></Link>
      <Link href="/capture/tasks" className="metric-card amber"><span><CalendarClock/>Open actions</span><strong>{summary.tasks?.open ?? 0}</strong><small>{summary.tasks?.overdue ?? 0} overdue</small><i><BellRing size={14}/> Needs attention</i></Link>
    </section>

    <section className="dashboard-layout">
      <div className="dashboard-primary">
        <section className="pro-panel market-radar">
          <header><div><span className="panel-kicker">MARKET RADAR</span><h2>Intelligence workspaces</h2><p>Live public data and capture workflows organized by the decisions you need to make.</p></div><Link href="/opportunities/federal-contracts">Explore all <ArrowRight size={15}/></Link></header>
          <div className="workspace-launch-grid">
            <Link href="/opportunities/federal-contracts"><span className="launch-icon blue"><Search/></span><div><b>Federal opportunities</b><small>Search active SAM.gov notices and save qualified work.</small><em>Open intelligence console <ArrowRight size={13}/></em></div></Link>
            <Link href="/awards/federal-contracts"><span className="launch-icon teal"><Award/></span><div><b>Award intelligence</b><small>Analyze recipients, agencies, obligations, and incumbents.</small><em>Explore USAspending <ArrowRight size={13}/></em></div></Link>
            <Link href="/participants/vendors"><span className="launch-icon violet"><Users/></span><div><b>Vendor intelligence</b><small>Research competitors, partners, UEIs, and award history.</small><em>Open vendor profiles <ArrowRight size={13}/></em></div></Link>
            <Link href="/participants/federal-agencies"><span className="launch-icon amber"><Building2/></span><div><b>Agency intelligence</b><small>Understand buying offices, spending, categories, and contacts.</small><em>View federal agencies <ArrowRight size={13}/></em></div></Link>
          </div>
        </section>

        <section className="pro-panel capture-board">
          <header><div><span className="panel-kicker">CAPTURE PIPELINE</span><h2>Pursuit distribution</h2></div><Link href="/capture/pipelines">Manage pipeline <ArrowRight size={14}/></Link></header>
          {stages.length ? <div className="pipeline-visual">{stages.map(([stage,count]) => <div key={stage}><span><b>{stage.replaceAll("_"," ")}</b><small>{count} pursuits</small></span><div><i style={{width:`${Math.max((count/total)*100,6)}%`}}/></div><strong>{Math.round((count/total)*100)}%</strong></div>)}</div> : <div className="empty-capture"><Target size={30}/><div><b>Your capture pipeline is ready.</b><p>Save a live opportunity, qualify it, and assign the next action.</p></div><Link href="/opportunities/federal-contracts">Start with live opportunities</Link></div>}
        </section>
      </div>

      <aside className="dashboard-secondary">
        <section className="pro-panel next-actions"><header><div><span className="panel-kicker">NEXT ACTIONS</span><h2>Workspace attention</h2></div></header>
          <Link href="/capture/tasks"><span><CalendarClock/></span><div><b>{summary.tasks?.open ?? 0} open tasks</b><small>{summary.tasks?.overdue ?? 0} overdue actions</small></div><ChevronRight/></Link>
          <Link href="/capture/saved-searches"><span><BellRing/></span><div><b>{summary.saved_searches ?? 0} saved searches</b><small>Monitor matching notices</small></div><ChevronRight/></Link>
          <Link href="/beacon/contacts"><span><Users/></span><div><b>{summary.contacts ?? 0} contacts</b><small>Government and industry relationships</small></div><ChevronRight/></Link>
          <Link href="/capture/teaming"><span><Handshake/></span><div><b>Teaming workspace</b><small>Track partners and requests</small></div><ChevronRight/></Link>
        </section>
        <section className="ai-card"><div className="ai-glow"/><Sparkles size={25}/><span>FORGEGOV AI</span><h3>Turn a solicitation into a capture plan.</h3><p>Summarize requirements, identify compliance risks, build a bid/no-bid brief, and create action items.</p><Link href="/assistant">Open AI workspace <ArrowRight size={15}/></Link></section>
      </aside>
    </section>
  </div>;
}
