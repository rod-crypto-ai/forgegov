"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  Bell,
  Bot,
  Check,
  ChevronRight,
  LayoutPanelLeft,
  LockKeyhole,
  Monitor,
  Moon,
  Palette,
  PlugZap,
  Unplug,
  MessagesSquare,
  CalendarDays,
  Mail,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Sun,
  UserRound,
} from "lucide-react";
import { apiGet, apiPatch, apiPost } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";
import { type AIResponseStyle, type DensityPreference, type ThemePreference, type UserPreferences, useThemePreferences } from "@/components/theme-provider";

type NotificationPreference = {
  in_app_enabled:boolean;
  email_enabled:boolean;
  immediate_critical:boolean;
  daily_digest:boolean;
  weekly_digest:boolean;
  opportunity_alerts:boolean;
  opportunity_changes:boolean;
  deadlines:boolean;
  pipeline:boolean;
  project_room:boolean;
  security:boolean;
};


type MicrosoftConnection = {
  provider:string;
  configured:boolean;
  connected:boolean;
  verified:boolean;
  verified_at?:string|null;
  status:string;
  account_email:string;
  scopes:string[];
  connected_at?:string|null;
  last_error?:string;
  default_team_id?:string;
  default_team_name?:string;
  default_channel_id?:string;
  default_channel_name?:string;
};
type MicrosoftTarget={id:string;name:string};

const notificationLabels: Array<[keyof NotificationPreference,string,string]> = [
  ["in_app_enabled", "In-app notifications", "Show intelligence and collaboration activity inside ForgeGov."],
  ["email_enabled", "Email delivery", "Allow ForgeGov to send enabled intelligence notifications by email."],
  ["immediate_critical", "Critical alerts", "Send critical deadline and security events immediately."],
  ["daily_digest", "Daily Intelligence Brief", "Receive one daily summary of relevant opportunity and capture activity."],
  ["weekly_digest", "Weekly Intelligence Brief", "Receive a weekly roll-up of intelligence and pursuit movement."],
];

export default function SettingsPage(){
  const {session}=useAuth();
  const {preferences,updatePreferences,reloadPreferences,resolvedTheme}=useThemePreferences();
  const [notification,setNotification]=useState<NotificationPreference|null>(null);
  const [message,setMessage]=useState("");
  const [busy,setBusy]=useState("");
  const [microsoft,setMicrosoft]=useState<MicrosoftConnection|null>(null);
  const [teams,setTeams]=useState<MicrosoftTarget[]>([]);
  const [channels,setChannels]=useState<MicrosoftTarget[]>([]);
  const [selectedTeam,setSelectedTeam]=useState("");
  const [selectedChannel,setSelectedChannel]=useState("");

  useEffect(()=>{
    let active=true;
    apiGet<NotificationPreference>("/notifications/preferences/").then(row=>{if(active)setNotification(row)}).catch(()=>{});
    const params=new URLSearchParams(window.location.search);
    const callbackState=params.get("microsoft");
    const callbackDetail=params.get("detail")??"";
    const loadStatus=()=>apiGet<MicrosoftConnection>("/integrations/microsoft/status/").then(row=>{if(!active)return row;setMicrosoft(row);setSelectedTeam(row.default_team_id??"");setSelectedChannel(row.default_channel_id??"");return row;});
    if(callbackState==="connected"){
      apiPost<MicrosoftConnection>("/integrations/microsoft/verify/",{}).then(row=>{if(!active)return;setMicrosoft(row);setSelectedTeam(row.default_team_id??"");setSelectedChannel(row.default_channel_id??"");setMessage(`Microsoft 365 connected and verified${row.account_email?` as ${row.account_email}`:""}.`)}).catch(error=>{if(!active)return;setMessage(`Microsoft sign-in returned, but ForgeGov could not verify the connection: ${error instanceof Error?error.message:"Unknown verification error"}`);void loadStatus().catch(()=>{})});
    }else{
      void loadStatus().catch(()=>{});
      if(callbackState==="error")Promise.resolve().then(()=>{if(active)setMessage(`Microsoft 365 connection failed: ${callbackDetail||"Microsoft did not complete authorization."}`)});
    }
    if(callbackState)window.history.replaceState({},"",`${window.location.pathname}#integrations`);
    return()=>{active=false};
  },[]);
  useEffect(()=>{if(!microsoft?.connected)return;apiGet<{results:MicrosoftTarget[]}>("/integrations/microsoft/teams/").then(row=>setTeams(row.results??[])).catch(()=>setTeams([]))},[microsoft?.connected]);
  useEffect(()=>{if(!microsoft?.connected||!selectedTeam)return;apiGet<{results:MicrosoftTarget[]}>(`/integrations/microsoft/channels/?team_id=${encodeURIComponent(selectedTeam)}`).then(row=>setChannels(row.results??[])).catch(()=>setChannels([]))},[microsoft?.connected,selectedTeam]);

  const appearanceSummary=useMemo(()=>`${preferences.theme === "system" ? `System (${resolvedTheme})` : preferences.theme} · ${preferences.density}`,[preferences.theme,preferences.density,resolvedTheme]);

  async function saveAppearance(patch:Partial<UserPreferences>){setBusy("appearance");setMessage("");try{await updatePreferences(patch);setMessage("Appearance preference saved.")}catch(error){setMessage(error instanceof Error?error.message:"Appearance could not be saved")}finally{setBusy("")}}
  async function saveAI(patch:Partial<UserPreferences>){setBusy("ai");setMessage("");try{await updatePreferences(patch);setMessage("ForgeGov AI preference saved.")}catch(error){setMessage(error instanceof Error?error.message:"AI preference could not be saved")}finally{setBusy("")}}
  async function toggleNotification(key:keyof NotificationPreference){if(!notification)return;const next={...notification,[key]:!notification[key]};setNotification(next);setBusy("notification");try{const remote=await apiPatch<NotificationPreference>("/notifications/preferences/",{[key]:next[key]});setNotification(remote);setMessage("Notification preference saved.")}catch(error){setNotification(notification);setMessage(error instanceof Error?error.message:"Notification preference could not be saved")}finally{setBusy("")}}

  async function connectMicrosoft(){setBusy("microsoft");setMessage("");try{const row=await apiPost<{authorization_url:string}>("/integrations/microsoft/connect/",{});window.location.assign(row.authorization_url)}catch(error){setMessage(error instanceof Error?error.message:"Microsoft 365 connection could not be started");setBusy("")}}
  async function verifyMicrosoft(){setBusy("microsoft-verify");setMessage("");try{const row=await apiPost<MicrosoftConnection>("/integrations/microsoft/verify/",{});setMicrosoft(row);setMessage(`Microsoft 365 connection verified${row.account_email?` as ${row.account_email}`:""}.`)}catch(error){setMessage(error instanceof Error?error.message:"Microsoft 365 connection could not be verified")}finally{setBusy("")}}
  async function disconnectMicrosoft(){if(!window.confirm("Disconnect your Microsoft 365 account from ForgeGov?"))return;setBusy("microsoft");try{await apiPost("/integrations/microsoft/disconnect/",{});const row=await apiGet<MicrosoftConnection>("/integrations/microsoft/status/");setMicrosoft(row);setTeams([]);setChannels([]);setMessage("Microsoft 365 disconnected.")}catch(error){setMessage(error instanceof Error?error.message:"Microsoft 365 could not be disconnected")}finally{setBusy("")}}
  async function saveMicrosoftDefaults(){if(!selectedTeam||!selectedChannel)return;const team=teams.find(row=>row.id===selectedTeam);const channel=channels.find(row=>row.id===selectedChannel);setBusy("microsoft-defaults");try{await apiPatch("/integrations/microsoft/defaults/",{default_team_id:selectedTeam,default_team_name:team?.name??"",default_channel_id:selectedChannel,default_channel_name:channel?.name??""});const row=await apiGet<MicrosoftConnection>("/integrations/microsoft/status/");setMicrosoft(row);setMessage("Default Teams destination saved.")}catch(error){setMessage(error instanceof Error?error.message:"Teams destination could not be saved")}finally{setBusy("")}}

  async function resetAppearance(){setBusy("reset");try{await updatePreferences({theme:"system",density:"comfortable",reduce_motion:false,sidebar_collapsed:false});await reloadPreferences();setMessage("Appearance reset to ForgeGov defaults.")}catch(error){setMessage(error instanceof Error?error.message:"Defaults could not be restored")}finally{setBusy("")}}

  return <main className="page-stack settings-page">
    <header className="feature-hero settings-hero"><div><span className="eyebrow">SETTINGS CENTER</span><h1>Make ForgeGov work the way you do</h1><p>Control appearance, AI research behavior, notifications, account security, and workspace preferences from one place.</p></div><div className="settings-current"><Palette size={18}/><div><span>Current appearance</span><strong>{appearanceSummary}</strong></div></div></header>
    {message&&<div className="system-banner settings-message"><Check size={16}/>{message}</div>}

    <div className="settings-layout">
      <nav className="settings-nav" aria-label="Settings sections">
        <a href="#appearance"><Palette/>Appearance</a>
        <a href="#ai"><Sparkles/>ForgeGov AI</a>
        <a href="#notifications"><Bell/>Notifications</a>
        <a href="#integrations"><PlugZap/>Connected Apps</a>
        <a href="#account"><UserRound/>Account & workspace</a>
        <a href="#security"><ShieldCheck/>Security</a>
      </nav>

      <div className="settings-content">
        <section id="appearance" className="data-panel settings-section">
          <div className="panel-heading"><Palette/><div><h2>Appearance</h2><p>Theme and layout preferences apply across the authenticated ForgeGov experience.</p></div></div>
          <div className="settings-block"><div><strong>Theme</strong><p>Follow your device automatically or lock ForgeGov to light or dark mode.</p></div><div className="theme-choice-grid">
            {([['system','System',Monitor],['light','Light',Sun],['dark','Dark',Moon]] as const).map(([value,label,Icon])=><button key={value} className={preferences.theme===value?"active":""} onClick={()=>void saveAppearance({theme:value as ThemePreference})}><Icon/><span><b>{label}</b><small>{value==='system'?'Match macOS / browser':value==='light'?'Bright workspace':'Low-light workspace'}</small></span>{preferences.theme===value&&<Check/>}</button>)}
          </div></div>
          <div className="settings-row"><div><strong>Interface density</strong><p>Comfortable gives controls more breathing room; Compact fits more capture data on screen.</p></div><select value={preferences.density} onChange={e=>void saveAppearance({density:e.target.value as DensityPreference})}><option value="comfortable">Comfortable</option><option value="compact">Compact</option></select></div>
          <label className="settings-toggle"><div><strong>Reduce motion</strong><p>Minimize animated transitions and smooth scrolling throughout the interface.</p></div><input type="checkbox" checked={preferences.reduce_motion} onChange={e=>void saveAppearance({reduce_motion:e.target.checked})}/><span/></label>
          <label className="settings-toggle"><div><strong>Start with sidebar collapsed</strong><p>Use the narrow navigation layout when a new authenticated session loads.</p></div><input type="checkbox" checked={preferences.sidebar_collapsed} onChange={e=>void saveAppearance({sidebar_collapsed:e.target.checked})}/><span/></label>
          <div className="settings-footer"><button className="secondary-button" disabled={busy==="reset"} onClick={()=>void resetAppearance()}><RefreshCw size={15}/>Restore appearance defaults</button></div>
        </section>

        <section id="ai" className="data-panel settings-section">
          <div className="panel-heading"><Bot/><div><h2>ForgeGov AI & Capture Copilot</h2><p>These settings change how AI requests are prepared on the server. They do not change the underlying government or workspace records.</p></div></div>
          <div className="settings-row"><div><strong>Response depth</strong><p>Choose how much explanation the AI should provide by default.</p></div><select value={preferences.ai_response_style} onChange={e=>void saveAI({ai_response_style:e.target.value as AIResponseStyle})}><option value="concise">Concise</option><option value="balanced">Balanced</option><option value="detailed">Detailed</option></select></div>
          <label className="settings-toggle"><div><strong>Live web research</strong><p>Allow ForgeGov AI to add SearXNG web evidence when the server has live web research configured.</p></div><input type="checkbox" checked={preferences.ai_live_web_enabled} onChange={e=>void saveAI({ai_live_web_enabled:e.target.checked})}/><span/></label>
          <label className="settings-toggle"><div><strong>Private workspace grounding</strong><p>Allow AI requests to use authorized pipeline, pursuit, task, contact, and file context from your active workspace.</p></div><input type="checkbox" checked={preferences.ai_workspace_grounding_enabled} onChange={e=>void saveAI({ai_workspace_grounding_enabled:e.target.checked})}/><span/></label>
          <div className="settings-callout"><LockKeyhole/><p>Disabling private workspace grounding removes private workspace records from new AI grounding requests. Public opportunity and award evidence can still be used.</p></div>
          <div className="settings-footer"><Link className="primary-button" href="/assistant"><Sparkles size={15}/>Open ForgeGov AI</Link></div>
        </section>

        <section id="notifications" className="data-panel settings-section">
          <div className="panel-heading"><Bell/><div><h2>Notifications</h2><p>Control the delivery channels and intelligence brief cadence added in v3.1.2.</p></div></div>
          {notification?<div className="settings-toggle-list">{notificationLabels.map(([key,label,description])=><label className="settings-toggle" key={key}><div><strong>{label}</strong><p>{description}</p></div><input type="checkbox" disabled={busy==="notification"} checked={Boolean(notification[key])} onChange={()=>void toggleNotification(key)}/><span/></label>)}</div>:<div className="table-state compact-state"><RefreshCw className="spin"/><strong>Loading notification preferences…</strong></div>}
          <div className="settings-footer"><Link className="secondary-button" href="/notifications">Open full Notification Center<ChevronRight size={15}/></Link></div>
        </section>


        <section id="integrations" className="data-panel settings-section">
          <div className="panel-heading"><PlugZap/><div><h2>Connected Apps</h2><p>Connect external work tools without giving ForgeGov organization-wide mailbox access.</p></div></div>
          <article className="connected-app-card">
            <div className="connected-app-heading"><div className="connected-app-icon"><span>M</span></div><div><strong>Microsoft 365</strong><p>Outlook email, Outlook Calendar, and Microsoft Teams actions directly from opportunity workspaces.</p></div><span className={`connected-app-state ${microsoft?.connected?"connected":microsoft?.configured?"available":"unavailable"}`}>{microsoft?.connected?(microsoft.verified?"Connected · Verified":"Connected · Verify"):microsoft?.configured?"Ready to connect":"Admin setup required"}</span></div>
            {microsoft?.connected?<><div className="connected-app-account"><div><span>Signed in account</span><strong>{microsoft.account_email||"Microsoft account"}</strong><small>{microsoft.verified?`Verified${microsoft.verified_at?` · ${new Date(microsoft.verified_at).toLocaleString()}`:""}`:"Connection saved, live verification still required"}</small></div><div className="connected-app-capabilities"><span><Mail/>Send Outlook mail</span><span><CalendarDays/>Create calendar events</span><span><MessagesSquare/>Share to Teams</span></div></div>
              {!microsoft.verified&&<div className="settings-footer"><span>Verify the saved Microsoft authorization against Microsoft Graph before using opportunity actions.</span><button className="secondary-button" disabled={busy==="microsoft-verify"} onClick={()=>void verifyMicrosoft()}><RefreshCw size={15}/>{busy==="microsoft-verify"?"Verifying…":"Verify connection"}</button></div>}
              <div className="settings-row microsoft-default-row"><div><strong>Default Teams destination</strong><p>ForgeGov uses this channel when you choose Share to Teams from an opportunity.</p></div><div className="microsoft-destination-controls"><select value={selectedTeam} onChange={e=>{setSelectedTeam(e.target.value);setSelectedChannel("");setChannels([])}}><option value="">Choose Team</option>{teams.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select><select value={selectedChannel} onChange={e=>setSelectedChannel(e.target.value)} disabled={!selectedTeam}><option value="">Choose channel</option>{channels.map(row=><option key={row.id} value={row.id}>{row.name}</option>)}</select><button className="secondary-button" disabled={!selectedTeam||!selectedChannel||busy==="microsoft-defaults"} onClick={()=>void saveMicrosoftDefaults()}>Save destination</button></div></div>
              {microsoft.last_error&&<div className="system-banner warning">Last Microsoft error: {microsoft.last_error}</div>}
              <div className="settings-footer"><span>Delegated permissions only · tokens encrypted server-side</span><button className="secondary-button danger-button" disabled={busy==="microsoft"} onClick={()=>void disconnectMicrosoft()}><Unplug size={15}/>Disconnect Microsoft 365</button></div></>:<div className="connected-app-connect"><div><strong>{microsoft?.configured?"Connect your Microsoft account":"Administrator configuration required"}</strong><p>{microsoft?.configured?"You will sign in through Microsoft and choose the account ForgeGov may use for delegated actions.":"Set MICROSOFT_CLIENT_ID, MICROSOFT_CLIENT_SECRET, and the callback URI in the ForgeGov deployment before users can connect."}</p></div><button className="primary-button" disabled={!microsoft?.configured||busy==="microsoft"} onClick={()=>void connectMicrosoft()}><PlugZap size={15}/>{busy==="microsoft"?"Opening Microsoft…":"Connect Microsoft 365"}</button></div>}
          </article>
        </section>

        <section id="account" className="data-panel settings-section">
          <div className="panel-heading"><UserRound/><div><h2>Account & workspace</h2><p>Your personal identity and company profile remain separate from UI preferences.</p></div></div>
          <div className="settings-link-list"><Link href="/account"><UserRound/><div><strong>Personal profile & company information</strong><span>{session?.user.email} · {session?.organization.name}</span></div><ChevronRight/></Link><Link href="/company"><LayoutPanelLeft/><div><strong>Company Hub</strong><span>Company profile, team, invitations, and relationships</span></div><ChevronRight/></Link>{session?.capabilities?.company_admin&&<Link href="/team"><SlidersHorizontal/><div><strong>Team administration</strong><span>Roles and authorized company membership</span></div><ChevronRight/></Link>}</div>
        </section>

        <section id="security" className="data-panel settings-section">
          <div className="panel-heading"><ShieldCheck/><div><h2>Security & sessions</h2><p>Sensitive authentication controls stay in the dedicated Security Center.</p></div></div>
          <div className="settings-link-list"><Link href="/security"><ShieldCheck/><div><strong>Security Center</strong><span>MFA, passkeys, recovery codes, sessions, and company security policy</span></div><ChevronRight/></Link><Link href="/forgot-password"><LockKeyhole/><div><strong>Password reset</strong><span>Start the verified password recovery workflow</span></div><ChevronRight/></Link></div>
        </section>
      </div>
    </div>
  </main>
}
