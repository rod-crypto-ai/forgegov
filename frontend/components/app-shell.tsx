"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { Bell, ChevronDown, ChevronRight, Command, Menu, PanelLeftClose, PanelLeftOpen, Search, Sparkles, X } from "lucide-react";
import { navigationGroups, utilityItems } from "@/lib/navigation";
import { useAuth } from "@/components/auth-provider";
import { apiGet } from "@/lib/api";
import { PlatformAdminNav } from "@/components/platform-admin-nav";
import { BetaFeedbackButton } from "@/components/beta-feedback";
import { useThemePreferences } from "@/components/theme-provider";

type SearchHit={type:string;id:string|number;title:string;subtitle?:string;href:string};

function navHrefActive(pathname:string,queryString:string,href:string){
  const [targetPath,targetQuery=""]=href.split("?");
  if(!(pathname===targetPath||pathname.startsWith(targetPath+"/")))return false;
  const current=new URLSearchParams(queryString);
  if(!targetQuery){if(targetPath==="/network"){const tab=current.get("tab");return !tab||tab==="directory";}return true;}
  const expected=new URLSearchParams(targetQuery);
  for(const [key,value] of expected.entries()){if(current.get(key)!==value)return false;}
  return true;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname(); const searchParams=useSearchParams(); const queryString=searchParams.toString(); const { session, workspaces, switchWorkspace, logout } = useAuth(); const { preferences, updatePreferences } = useThemePreferences(); const router = useRouter();
  const [query,setQuery]=useState(""); const [menuOpen,setMenuOpen]=useState(false); const [workspaceOpen,setWorkspaceOpen]=useState(false); const [responsiveCompact,setResponsiveCompact]=useState(false); const [hits,setHits]=useState<SearchHit[]>([]); const [searching,setSearching]=useState(false); const [searchOpen,setSearchOpen]=useState(false); const [unreadAlerts,setUnreadAlerts]=useState(0); const [unreadCollaboration,setUnreadCollaboration]=useState(0);
  const collapsed=preferences.sidebar_collapsed;
  const effectiveCollapsed=collapsed||responsiveCompact;
  // v3.2.1.3 responsive shell state: tablets/smaller laptops use an icon rail, not the mobile drawer.
  const [expanded,setExpanded]=useState<Record<string,boolean>>(()=>Object.fromEntries(navigationGroups.map(g=>[g.label,["Capture","Opportunities","Awards"].includes(g.label)])));
  const visibleNavigationGroups=useMemo(()=>navigationGroups.map(group=>({
    ...group,
    items:group.items.filter(item=>item.href!=="/reports/executive"||Boolean(session?.capabilities?.executive_financial)),
  })),[session?.capabilities?.executive_financial]);
  const activeGroup=useMemo(()=>visibleNavigationGroups.find(g=>g.items.some(i=>navHrefActive(pathname,queryString,i.href))),[pathname,queryString,visibleNavigationGroups]);

  useEffect(()=>{
    const compactQuery=window.matchMedia("(min-width:901px) and (max-width:1180px)");
    const desktopQuery=window.matchMedia("(min-width:901px)");
    const sync=()=>{
      setResponsiveCompact(compactQuery.matches);
      if(desktopQuery.matches)setMenuOpen(false);
    };
    const timer=window.setTimeout(sync,0);
    compactQuery.addEventListener("change",sync);
    desktopQuery.addEventListener("change",sync);
    return()=>{
      window.clearTimeout(timer);
      compactQuery.removeEventListener("change",sync);
      desktopQuery.removeEventListener("change",sync);
    };
  },[]);

  function toggleSidebar(){
    if(effectiveCollapsed){
      setResponsiveCompact(false);
      if(collapsed)void updatePreferences({sidebar_collapsed:false}).catch(()=>{});
      return;
    }
    void updatePreferences({sidebar_collapsed:true}).catch(()=>{});
  }
  function toggleGroup(label:string,isExpanded:boolean){
    if(effectiveCollapsed){
      setResponsiveCompact(false);
      if(collapsed)void updatePreferences({sidebar_collapsed:false}).catch(()=>{});
      setExpanded(current=>({...current,[label]:true}));
      return;
    }
    setExpanded(current=>({...current,[label]:!isExpanded}));
  }
  useEffect(()=>{const onKey=(event:KeyboardEvent)=>{if((event.metaKey||event.ctrlKey)&&event.key.toLowerCase()==="k"){event.preventDefault();document.getElementById("forge-global-search")?.focus();}};window.addEventListener("keydown",onKey);return()=>window.removeEventListener("keydown",onKey)},[]);
  useEffect(()=>{const value=query.trim();const timer=window.setTimeout(()=>{if(value.length<2){setHits([]);setSearching(false);return;}setSearching(true);apiGet<{results:SearchHit[]}>(`/intelligence/search/?q=${encodeURIComponent(value)}&limit=6`).then(r=>{setHits(r.results??[]);setSearchOpen(true)}).catch(()=>setHits([])).finally(()=>setSearching(false))},value.length<2?0:220);return()=>window.clearTimeout(timer)},[query]);
  useEffect(()=>{let active=true;const load=()=>Promise.all([apiGet<{results?:unknown[]}|unknown[]>("/alerts/?read=false&dismissed=false&page_size=100"),apiGet<{results?:Array<{read:boolean}>}|Array<{read:boolean}>>("/collaboration/notifications/?page_size=100"),apiGet<unknown[]>("/auth/invitations/pending/")]).then(([alerts,notifications,pendingInvites])=>{if(!active)return;const alertRows=Array.isArray(alerts)?alerts:(alerts.results??[]);const notificationRows=Array.isArray(notifications)?notifications:(notifications.results??[]);setUnreadAlerts(alertRows.length);setUnreadCollaboration(notificationRows.filter(row=>!row.read).length+(Array.isArray(pendingInvites)?pendingInvites.length:0))}).catch(()=>{});void load();const timer=window.setInterval(load,60000);return()=>{active=false;window.clearInterval(timer)}},[pathname]);
  function submit(event:React.FormEvent){event.preventDefault();const value=query.trim();setSearchOpen(false);router.push(value?`/search?q=${encodeURIComponent(value)}`:"/search")}
  function liveSearch(source:"contracts"|"grants"){const value=query.trim();setSearchOpen(false);router.push(`/${source==="grants"?"opportunities/federal-grants":"opportunities/federal-contracts"}${value?`?q=${encodeURIComponent(value)}&auto=1`:""}`)}
  function choose(hit:SearchHit){setSearchOpen(false);setQuery("");router.push(hit.href)}
  if(["/sign-in","/register","/forgot-password"].includes(pathname)||(pathname==="/"&&!session))return <>{children}</>;
  const initials=`${session?.user.first_name?.[0]??""}${session?.user.last_name?.[0]??""}`||session?.user.email?.[0]?.toUpperCase()||"U";
  const displayName=`${session?.user.first_name??""} ${session?.user.last_name??""}`.trim()||session?.user.email||"ForgeGov user";
  return <div className={`forge-shell ${effectiveCollapsed?"sidebar-collapsed":""}`}>
    <aside className={`forge-sidebar ${menuOpen?"open":""} ${effectiveCollapsed?"collapsed":""}`}><div className="forge-brandbar"><Link href="/" className="forge-brand" onClick={()=>setMenuOpen(false)}><span className="forge-logo"><span>F</span>G</span><span><b>FORGE</b>GOV<small>GovCon Intelligence</small></span></Link><button className="shell-icon mobile-only" onClick={()=>setMenuOpen(false)} aria-label="Close navigation"><X size={20}/></button></div>
      <div className="workspace-switcher-wrap"><button className="workspace-switcher" onClick={()=>setWorkspaceOpen(value=>!value)} aria-expanded={workspaceOpen}><span className="workspace-avatar">{session?.organization.name.slice(0,2).toUpperCase()}</span><span><b>{session?.organization.name}</b><small>{workspaces.length>1?`${workspaces.length} authorized workspaces`:"Company workspace"}</small></span><ChevronDown size={16}/></button>{workspaceOpen&&<div className="workspace-menu"><strong className="workspace-menu-label">Switch workspace</strong>{workspaces.map(row=><button key={row.organization.id} className={row.organization.id===session?.organization.id?"active":""} onClick={()=>{setWorkspaceOpen(false);void switchWorkspace(row.organization.id)}}><span>{row.organization.name}</span><small>{row.role}</small></button>)}<hr/><Link href="/company" onClick={()=>setWorkspaceOpen(false)}>Company Hub</Link><Link href="/account" onClick={()=>setWorkspaceOpen(false)}>Personal profile</Link><Link href="/settings" onClick={()=>setWorkspaceOpen(false)}>Workspace settings</Link></div>}</div>
      <Link href="/assistant" className={`ai-launch ${pathname==="/assistant"?"active":""}`} onClick={()=>setMenuOpen(false)}><Sparkles size={18}/><span><b>ForgeGov AI</b><small>Research & capture copilot</small></span><ChevronRight size={16}/></Link>
      <nav className="forge-nav">{visibleNavigationGroups.map(group=>{const Icon=group.icon;const isActive=activeGroup?.label===group.label;const isExpanded=expanded[group.label]||isActive;return <section className={`forge-nav-group ${isActive?"active-group":""}`} key={group.label}><button onClick={()=>toggleGroup(group.label,isExpanded)}><span><Icon size={18}/><span className="forge-nav-label">{group.label}</span></span>{isExpanded?<ChevronDown size={15}/>:<ChevronRight size={15}/>}</button>{isExpanded&&<div>{group.items.map(item=><Link key={item.href} href={item.href} onClick={()=>setMenuOpen(false)} className={navHrefActive(pathname,queryString,item.href)?"active":""}>{item.label}</Link>)}</div>}</section>})}</nav>
      <div className="forge-sidebar-footer">
        <PlatformAdminNav />{utilityItems.map(item=>{const Icon=item.icon;return <Link href={item.href} key={item.href} className={navHrefActive(pathname,queryString,item.href)?"active":""}>{Icon&&<Icon size={17}/>}<span className="forge-footer-label">{item.label}</span></Link>})}</div>
    </aside>{menuOpen&&<button className="shell-backdrop" onClick={()=>setMenuOpen(false)} aria-label="Close navigation"/>}
    <main className="forge-main"><header className="forge-topbar"><div className="topbar-left"><button className="shell-icon mobile-only" onClick={()=>setMenuOpen(true)} aria-label="Open navigation"><Menu size={21}/></button><button className="shell-icon desktop-sidebar-toggle" onClick={toggleSidebar} aria-label={effectiveCollapsed?"Expand sidebar":"Collapse sidebar"}>{effectiveCollapsed?<PanelLeftOpen size={20}/>:<PanelLeftClose size={20}/>}</button><div className="global-search-wrap"><form className="command-search" onSubmit={submit}><Search size={18}/><input id="forge-global-search" value={query} onFocus={()=>setSearchOpen(true)} onChange={e=>setQuery(e.target.value)} placeholder="Search opportunities, pursuits, rooms, documents, companies..."/><kbd><Command size={12}/> K</kbd></form>{searchOpen&&query.trim().length>=2&&<div className="global-search-results">{searching?<p>Searching ForgeGov…</p>:<>{hits.length?hits.map(hit=><button className={`global-search-hit hit-${hit.type}`} key={`${hit.type}-${hit.id}`} onClick={()=>choose(hit)}><span>{hit.type}</span><strong>{hit.title}</strong><small>{hit.subtitle||"Open in ForgeGov"}</small></button>):<p>No indexed ForgeGov matches yet.</p>}<div className="global-live-search-actions"><button type="button" onClick={()=>liveSearch("contracts")}><span>LIVE SAM.GOV</span><strong>Search contract opportunities</strong></button><button type="button" onClick={()=>liveSearch("grants")}><span>LIVE GRANTS.GOV</span><strong>Search federal grants</strong></button></div></>}</div>}</div></div><div className="topbar-actions"><span className="live-source"><i/> Federal data workspace</span><button className="shell-icon notification-button" onClick={()=>router.push("/notifications")} aria-label={`${unreadAlerts+unreadCollaboration} unread notifications`}><Bell size={19}/>{unreadAlerts+unreadCollaboration>0&&<span className="notification-count">{unreadAlerts+unreadCollaboration>99?"99+":unreadAlerts+unreadCollaboration}</span>}</button><button className="user-chip" onClick={()=>router.push("/account")}><span>{initials}</span><div><b>{displayName}</b><small>{session?.role}</small></div><ChevronDown size={14}/></button><button className="toolbar-button" onClick={()=>void logout()}>Sign out</button></div></header><div className="forge-content" onClick={()=>setSearchOpen(false)}>{children}</div><BetaFeedbackButton/></main>
  </div>;
}
