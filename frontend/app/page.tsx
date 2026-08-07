"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  ArrowRight, Award, BellRing, Building2, CalendarClock, ChevronRight,
  CircleDollarSign, Database, FileSearch, Handshake, Radar, Search,
  ShieldCheck, Sparkles, Target, TrendingUp, Users, FolderKanban, BrainCircuit,
} from "lucide-react";
import { apiGet } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

type Summary = { opportunities?: { total?: number; active?: number }; awards?: { total?: number; obligated_total?: number }; pipeline?: { total?: number; by_stage?: Record<string, number>; weighted_value?: number }; pursuits?: { total?: number }; tasks?: { open?: number; overdue?: number }; contacts?: number; vendors?: number; agencies?: number; saved_searches?: number; };
type CommandCenter={metrics:{pipeline:number;active_rooms:number;open_tasks:number;overdue:number;unread_alerts:number;pending_invitations:number;weighted_pipeline?:number};intelligence?:{recent_awards_30d:number;stored_awards:number;latest_award_sync:string|null;latest_award_sync_status:string;connectors:{healthy:number;attention:number;total:number};top_award_recipients:Array<{recipient_name:string;awards:number;obligated:number}>};deadlines:Array<{type:string;title:string;subtitle?:string;due_at:string;href:string;overdue:boolean}>;activity:Array<{type:string;title:string;subtitle?:string;created_at:string;href:string}>;insights:Array<{severity:string;title:string;detail:string;href:string}>;quick_actions:Array<{label:string;href:string}>};
type Integrations = { sam_gov?: { configured?: boolean }; usaspending?: { reachable?: boolean; stored_awards?: number }; ai?: { web_search_configured?: boolean; web_search_reachable?: boolean | null; web_search_status?: string } };
const money = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });

export default function DashboardPage() {
  const { session } = useAuth();
  const [summary, setSummary] = useState<Summary>({});
  const [integrations, setIntegrations] = useState<Integrations>({});
  const [commandCenter,setCommandCenter]=useState<CommandCenter>({metrics:{pipeline:0,active_rooms:0,open_tasks:0,overdue:0,unread_alerts:0,pending_invitations:0},deadlines:[],activity:[],insights:[],quick_actions:[]});
  const [error, setError] = useState("");
  useEffect(() => { Promise.all([apiGet<Summary>("/dashboard/summary/"), apiGet<Integrations>("/integrations/status/?probe=true"), apiGet<CommandCenter>("/dashboard/command-center/")]).then(([a,b,c]) => {setSummary(a); setIntegrations(b); setCommandCenter(c);}).catch((e) => setError(e instanceof Error ? e.message : "Backend unavailable")); }, []);
  const stages = useMemo(() => Object.entries(summary.pipeline?.by_stage ?? {}), [summary]);
  const total = Math.max(summary.pipeline?.total ?? 0, 1);
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const displayName = session?.user.first_name?.trim() || session?.user.email?.split("@")[0] || "there";

  return <div className="executive-dashboard">
    <section className="executive-head">
      <div>
        <span className="page-kicker">CAPTURE COMMAND CENTER</span>
        <h1>{greeting}, {displayName}.</h1>
        <p>Find the right work, understand the market, and move every pursuit forward from one operating picture.</p>
      </div>
      <div className="head-actions"><Link href="/assistant" className="button ghost"><Sparkles size={17}/> Ask ForgeGov AI</Link><Link href="/opportunities/federal-contracts" className="button solid"><Search size={17}/> Find opportunities</Link></div>
    </section>

    {error && <div className="alert-strip"><ShieldCheck size={18}/><div><b>ForgeGov is running, but the API did not respond.</b><span>{error}</span></div></div>}

    <section className="data-status-strip">
      <div><i className={integrations.sam_gov?.configured ? "ok" : "warn"}/><span><b>SAM.gov</b><small>{integrations.sam_gov?.configured ? "Live search ready" : "API key required"}</small></span></div>
      <div><i className={integrations.usaspending?.reachable ? "ok" : "warn"}/><span><b>USAspending</b><small>{integrations.usaspending?.reachable ? "Live award data" : "Connection unavailable"}</small></span></div>
      <div><i className="ok"/><span><b>Grants.gov</b><small>Public grant search active</small></span></div>
      <div><i className={integrations.ai?.web_search_status === "live" || integrations.ai?.web_search_reachable ? "ok" : "warn"}/><span><b>Live web</b><small>{integrations.ai?.web_search_status === "live" || integrations.ai?.web_search_reachable ? "SearXNG connected" : integrations.ai?.web_search_status === "invalid_response" ? "Invalid response" : integrations.ai?.web_search_status === "unavailable" ? "Service unavailable" : integrations.ai?.web_search_configured ? "Configured" : "Setup available"}</small></span></div>
      <div><Database size={17}/><span><b>{integrations.usaspending?.stored_awards ?? summary.awards?.total ?? 0} awards indexed</b><small>Stored in ForgeGov</small></span></div>
      <Link href="/intelligence/connectors">Manage data sources <ChevronRight size={15}/></Link>
    </section>

    <section className="command-center-grid">
      <div className="command-panel command-insights"><header><div><span className="panel-kicker">FORGEAI WORKSPACE SIGNALS</span><h2>What needs attention</h2></div><Link href="/assistant">Ask AI <ArrowRight size={14}/></Link></header><div>{commandCenter.insights.map((row,index)=><Link href={row.href} className={`command-insight severity-${row.severity}`} key={`${row.title}-${index}`}><i/><span><b>{row.title}</b><small>{row.detail}</small></span><ChevronRight size={16}/></Link>)}</div></div>
      <div className="command-panel command-deadlines"><header><div><span className="panel-kicker">DEADLINES</span><h2>Upcoming work</h2></div><Link href="/capture/tasks">All tasks <ArrowRight size={14}/></Link></header><div>{commandCenter.deadlines.length?commandCenter.deadlines.slice(0,5).map((row,index)=><Link href={row.href} key={`${row.type}-${index}`} className={row.overdue?"overdue":""}><CalendarClock size={17}/><span><b>{row.title}</b><small>{row.subtitle||row.type.replaceAll("_"," ")}</small></span><time>{new Date(row.due_at).toLocaleDateString()}</time></Link>):<p className="command-empty">No scheduled deadlines yet.</p>}</div></div>
      <div className="command-panel command-activity"><header><div><span className="panel-kicker">RECENT ACTIVITY</span><h2>Workspace movement</h2></div><Link href="/audit-log">Audit log <ArrowRight size={14}/></Link></header><div>{commandCenter.activity.length?commandCenter.activity.slice(0,6).map((row,index)=><Link href={row.href} key={`${row.type}-${index}`}><span className={`activity-dot ${row.type}`}/><span><b>{row.title}</b><small>{row.subtitle||row.type}</small></span><time>{new Date(row.created_at).toLocaleDateString()}</time></Link>):<p className="command-empty">Activity will appear as your team works.</p>}</div></div>
    </section>

    <section className="mission-intelligence-strip">
      <div><span className="panel-kicker">INTELLIGENCE PULSE</span><strong>{commandCenter.intelligence?.recent_awards_30d ?? 0}</strong><small>award records refreshed in the last 30 days</small></div>
      <div><span className="panel-kicker">WEIGHTED PIPELINE</span><strong>{money.format(commandCenter.metrics.weighted_pipeline ?? summary.pipeline?.weighted_value ?? 0)}</strong><small>probability-adjusted pursuit value</small></div>
      <div><span className="panel-kicker">CONNECTOR HEALTH</span><strong>{commandCenter.intelligence?.connectors.healthy ?? 0}/{commandCenter.intelligence?.connectors.total ?? 0}</strong><small>{commandCenter.intelligence?.connectors.attention ? `${commandCenter.intelligence.connectors.attention} source(s) need attention` : "enabled sources reporting normally"}</small></div>
      <div><span className="panel-kicker">AWARD FRESHNESS</span><strong>{commandCenter.intelligence?.latest_award_sync_status?.replaceAll("_"," ") ?? "not run"}</strong><small>{commandCenter.intelligence?.latest_award_sync ? `Last sync ${new Date(commandCenter.intelligence.latest_award_sync).toLocaleString()}` : "Run USAspending ingestion to populate market evidence"}</small></div>
      <Link href="/intelligence/awards">Open award intelligence <ArrowRight size={14}/></Link>
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
            <Link className="workspace-launch-project" href="/project-rooms"><span className="launch-icon violet"><FolderKanban/></span><div><b>Project Rooms</b><small>Manage tasks, discussions, internal notes, controlled files, and approved partner-company access.</small><em>Open secure collaboration <ArrowRight size={13}/></em></div></Link>
            <Link className="workspace-launch-contract" href="/opportunities/federal-contracts"><span className="launch-icon blue"><Search/></span><div><b>Federal contract opportunities</b><small>Search active SAM.gov notices and open full opportunity workspaces.</small><em>Search live contracts <ArrowRight size={13}/></em></div></Link>
            <Link className="workspace-launch-grant" href="/opportunities/federal-grants"><span className="launch-icon teal"><FileSearch/></span><div><b>Federal grant opportunities</b><small>Search Grants.gov, review application details, and use contextual AI.</small><em>Search live grants <ArrowRight size={13}/></em></div></Link>
            <Link className="workspace-launch-subnet" href="/opportunities/subcontracting"><span className="launch-icon violet"><Handshake/></span><div><b>Subcontracting opportunities</b><small>Review current SBA SUBNet listings and reported SAM subawards.</small><em>Open subcontracting <ArrowRight size={13}/></em></div></Link>
            <Link href="/opportunities/federal-forecasts"><span className="launch-icon amber"><Radar/></span><div><b>Procurement forecasts</b><small>Review forward-looking agency acquisition sources and activity.</small><em>Open forecast feed <ArrowRight size={13}/></em></div></Link>
            <Link href="/opportunities/federal-vehicles"><span className="launch-icon blue"><Database/></span><div><b>Contract vehicles</b><small>Explore IDIQ, BPA, and vehicle-holder intelligence.</small><em>Search vehicles <ArrowRight size={13}/></em></div></Link>
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
