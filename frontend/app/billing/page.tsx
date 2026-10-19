"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { BadgeDollarSign, CalendarClock, CheckCircle2, CreditCard, Gauge, LockKeyhole, RefreshCw, ShieldCheck } from "lucide-react";
import { apiGet, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

type BillingSummary = {
  organization:{id:number;name:string};
  subscription:{status:string;access_state:string;permits_access:boolean;provider:string;grandfathered:boolean;grandfathered_at:string|null;grandfathered_reason:string;seat_quantity:number;trial_available:boolean;trial_ends_at:string|null;current_period_starts_at:string|null;current_period_ends_at:string|null;grace_ends_at:string|null;cancel_at_period_end:boolean};
  plan:{code:string;name:string;description:string;currency:string;price_cents:number;billing_interval:string;entitlements:Record<string,boolean>;limits:Record<string,number|null>};
  offer:{code:string;name:string;description:string;currency:string;price_cents:number;billing_interval:string;trial_days:number};
  usage:Array<{metric:string;quantity:number;limit:number|null;period_starts_at:string;period_ends_at:string}>;
  billing:{provider:string;checkout_enabled:boolean;portal_enabled:boolean;checkout_available:boolean;portal_available:boolean;detail:string};
};

type HostedSession = {id:string;url:string};

function humanize(value:string){return value.replaceAll("_"," ").replace(/\b\w/g,char=>char.toUpperCase())}
function date(value:string|null){return value?new Date(value).toLocaleDateString():"Not scheduled"}
function price(cents:number,currency:string){return new Intl.NumberFormat("en-US",{style:"currency",currency,maximumFractionDigits:0}).format(cents/100)}

export default function BillingPage(){
  const {session}=useAuth();
  const [data,setData]=useState<BillingSummary|null>(null);
  const [loadError,setLoadError]=useState("");
  const [actionError,setActionError]=useState("");
  const [loading,setLoading]=useState(true);
  const [action,setAction]=useState<"checkout"|"portal"|"">("");
  const [notice]=useState(()=>{
    if(typeof window==="undefined")return "";
    const result=new URLSearchParams(window.location.search).get("checkout");
    if(result==="success")return "Checkout returned successfully. Access updates only after ForgeGov verifies the signed Stripe event.";
    if(result==="cancelled")return "Checkout was cancelled. No subscription change was made.";
    return "";
  });
  useEffect(()=>{let active=true;apiGet<BillingSummary>("/billing/summary/").then(row=>{if(active)setData(row)}).catch(reason=>{if(active)setLoadError(reason instanceof Error?reason.message:"Billing information could not be loaded.")}).finally(()=>{if(active)setLoading(false)});return()=>{active=false}},[]);

  async function openHostedPage(kind:"checkout"|"portal"){
    setAction(kind);setActionError("");
    try{
      const hosted=await apiPost<HostedSession>(`/billing/${kind}/`,{});
      window.location.assign(hosted.url);
    }catch(reason){
      setActionError(reason instanceof Error?reason.message:"The hosted billing page could not be opened.");
      setAction("");
    }
  }

  if(!session?.capabilities?.billing_admin)return <main className="page-stack billing-page"><section className="data-panel billing-denied"><LockKeyhole/><h1>Billing administrator access required</h1><p>Only workspace owners and administrators can view commercial terms and subscription status.</p><Link className="secondary-button" href="/settings">Return to settings</Link></section></main>;
  if(loading)return <main className="page-stack billing-page"><section className="table-state"><RefreshCw className="spin"/><strong>Loading workspace access…</strong></section></main>;
  if(loadError||!data)return <main className="page-stack billing-page"><section className="table-state"><CreditCard/><strong>Billing information is unavailable</strong><p>{loadError||"The workspace subscription could not be loaded."}</p></section></main>;

  const publishedPrice=data.plan.price_cents>0;
  const grandfathered=data.subscription.grandfathered;
  return <main className="page-stack billing-page" data-qa="billing-page">
    <header className="feature-hero billing-hero"><div><span className="eyebrow">WORKSPACE ADMINISTRATION</span><h1>Plan & billing</h1><p>Review access, commercial terms, entitlements, and measured usage for {data.organization.name}.</p></div><div className={`source-health-pill ${data.subscription.permits_access?"live":"reconnecting"}`}><span/>{data.subscription.permits_access?"Workspace access enabled":"Workspace access restricted"}</div></header>
    <section className="billing-summary-grid">
      <article className="data-panel billing-plan-card"><div className="billing-icon"><BadgeDollarSign/></div><span>Current plan</span><h2>{grandfathered?"Grandfathered ForgeGov Access":data.plan.name}</h2><p>{grandfathered?"Permanent founding-workspace access with no subscription payment required.":data.plan.description}</p><strong>{grandfathered?"No subscription payment required":publishedPrice?`${price(data.plan.price_cents,data.plan.currency)} / ${data.plan.billing_interval}`:"Commercial terms not published"}</strong></article>
      <article className="data-panel billing-stat"><ShieldCheck/><span>Access state</span><strong>{humanize(data.subscription.access_state)}</strong><small>{data.subscription.permits_access?"Authorized workspace access":"Contact ForgeGov support"}</small></article>
      <article className="data-panel billing-stat"><CalendarClock/><span>Current period</span><strong>{date(data.subscription.current_period_ends_at)}</strong><small>{data.subscription.cancel_at_period_end?"Ends after current period":"No cancellation scheduled"}</small></article>
      <article className="data-panel billing-stat"><Gauge/><span>Licensed seats</span><strong>{data.subscription.seat_quantity}</strong><small>Active seat quantity on record</small></article>
    </section>
    <div className="billing-detail-grid">
      <section className="data-panel billing-section"><div className="panel-title-row"><div><span className="eyebrow">ACCESS</span><h2>Included capabilities</h2></div><CheckCircle2/></div>{Object.keys(data.plan.entitlements).length?<div className="billing-list">{Object.entries(data.plan.entitlements).map(([key,enabled])=><div key={key}><span className={enabled?"enabled":"disabled"}><CheckCircle2/></span><strong>{humanize(key)}</strong><small>{enabled?"Included":"Not included"}</small></div>)}</div>:<div className="table-state compact-state"><strong>No restrictive entitlements configured</strong><p>Your early-access workspace retains its existing ForgeGov capabilities.</p></div>}</section>
      <section className="data-panel billing-section"><div className="panel-title-row"><div><span className="eyebrow">USAGE</span><h2>Current measurement window</h2></div><Gauge/></div>{data.usage.length?<div className="billing-list">{data.usage.map(row=><div key={row.metric}><span><Gauge/></span><strong>{humanize(row.metric)}</strong><small>{row.quantity}{row.limit==null?" used · no enforced limit":` of ${row.limit} used`}</small></div>)}</div>:<div className="table-state compact-state"><strong>No metered usage recorded</strong><p>ForgeGov is not enforcing usage limits for this workspace.</p></div>}</section>
    </div>
    <section className="data-panel billing-provider"><div><CreditCard/><div><span className="eyebrow">PAYMENT OPERATIONS</span><h2>{grandfathered?"Grandfathered workspace":data.billing.checkout_enabled?"Stripe-hosted billing available":"Automated billing is not enabled"}</h2><p>{grandfathered?"This workspace is permanently exempt from subscription charges. Checkout and billing management are disabled.":data.billing.detail}</p></div></div>{data.billing.checkout_available&&<div className="billing-offer"><strong>{data.offer.name}</strong><span>{price(data.offer.price_cents,data.offer.currency)} / {data.offer.billing_interval}{data.subscription.trial_available&&data.offer.trial_days?` · ${data.offer.trial_days}-day trial`:""}</span></div>}{notice&&<div className="settings-callout" role="status"><CheckCircle2/><p>{notice}</p></div>}{actionError&&<div className="settings-callout danger" role="alert"><LockKeyhole/><p>{actionError}</p></div>}<div className="billing-provider-facts"><span>Provider <strong>{grandfathered?"Not required":humanize(data.billing.provider)}</strong></span><span>Subscription payment <strong>{grandfathered?"Not required":data.billing.checkout_enabled?"Configured":"Unavailable"}</strong></span><span>Customer portal <strong>{grandfathered?"Not required":data.billing.portal_enabled?"Configured":"Unavailable"}</strong></span></div><div className="billing-actions">{data.billing.checkout_available&&<button className="primary-button" type="button" disabled={Boolean(action)} onClick={()=>openHostedPage("checkout")}>{action==="checkout"?<><RefreshCw className="spin"/>Opening secure checkout…</>:data.subscription.trial_available?`Start ${data.offer.trial_days}-day trial`:"Subscribe annually"}</button>}{data.billing.portal_available&&<button className="secondary-button" type="button" disabled={Boolean(action)} onClick={()=>openHostedPage("portal")}>{action==="portal"?<><RefreshCw className="spin"/>Opening customer portal…</>:"Manage billing"}</button>}</div><div className="settings-callout"><LockKeyhole/><p>{grandfathered?"Grandfathered access is recorded on this workspace and is not dependent on a payment provider.":"Checkout and payment management open on Stripe’s hosted pages. ForgeGov does not collect or store card details."}</p></div></section>
  </main>
}
