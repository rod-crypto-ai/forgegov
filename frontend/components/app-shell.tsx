"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import {
  ChevronDown, ChevronRight, CircleHelp, Command, Menu,
  Search, Sparkles, X,
} from "lucide-react";
import { navigationGroups, utilityItems } from "@/lib/navigation";
import { useAuth } from "@/components/auth-provider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { session, logout } = useAuth();
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(navigationGroups.map((group) => [group.label, ["Capture", "Opportunities", "Awards"].includes(group.label)])),
  );
  const activeGroup = useMemo(() => navigationGroups.find((group) => group.items.some((item) => pathname === item.href)), [pathname]);

  function submit(event: React.FormEvent) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/opportunities/federal-contracts?q=${encodeURIComponent(value)}&auto=1` : "/opportunities/federal-contracts");
  }

  if (pathname === "/sign-in" || pathname === "/register" || pathname === "/forgot-password") return <>{children}</>;

  const initials = `${session?.user.first_name?.[0] ?? ""}${session?.user.last_name?.[0] ?? ""}` || session?.user.email?.[0]?.toUpperCase() || "U";
  const displayName = `${session?.user.first_name ?? ""} ${session?.user.last_name ?? ""}`.trim() || session?.user.email || "ForgeGov user";

  return <div className="forge-shell">
    <aside className={`forge-sidebar ${menuOpen ? "open" : ""}`}>
      <div className="forge-brandbar">
        <Link href="/" className="forge-brand" onClick={() => setMenuOpen(false)}>
          <span className="forge-logo"><span>F</span>G</span>
          <span><b>FORGE</b>GOV<small>GovCon Intelligence</small></span>
        </Link>
        <button className="shell-icon mobile-only" onClick={() => setMenuOpen(false)} aria-label="Close navigation"><X size={20}/></button>
      </div>

      <div className="workspace-switcher" aria-label="Current workspace">
        <span className="workspace-avatar">{session?.organization.name.slice(0, 2).toUpperCase()}</span>
        <span><b>{session?.organization.name}</b><small>Primary workspace</small></span>
        <ChevronDown size={16}/>
      </div>

      <Link href="/assistant" className={`ai-launch ${pathname === "/assistant" ? "active" : ""}`} onClick={() => setMenuOpen(false)}>
        <Sparkles size={18}/><span><b>ForgeGov AI</b><small>Research & capture copilot</small></span><ChevronRight size={16}/>
      </Link>

      <nav className="forge-nav">
        {navigationGroups.map((group) => {
          const Icon = group.icon;
          const isActive = activeGroup?.label === group.label;
          const isExpanded = expanded[group.label] || isActive;
          return <section className={`forge-nav-group ${isActive ? "active-group" : ""}`} key={group.label}>
            <button onClick={() => setExpanded((current) => ({...current, [group.label]: !isExpanded}))}>
              <span><Icon size={18}/>{group.label}</span>{isExpanded ? <ChevronDown size={15}/> : <ChevronRight size={15}/>} 
            </button>
            {isExpanded && <div>{group.items.map((item) => <Link key={item.href} href={item.href} onClick={() => setMenuOpen(false)} className={pathname === item.href ? "active" : ""}>{item.label}</Link>)}</div>}
          </section>;
        })}
      </nav>

      <div className="forge-sidebar-footer">
        {utilityItems.map((item) => { const Icon = item.icon; return <Link href={item.href} key={item.href} className={pathname === item.href ? "active" : ""}>{Icon && <Icon size={17}/>} {item.label}</Link>; })}
        <Link href="/settings"><CircleHelp size={17}/> Help center</Link>
      </div>
    </aside>

    {menuOpen && <button className="shell-backdrop" onClick={() => setMenuOpen(false)} aria-label="Close navigation"/>}

    <main className="forge-main">
      <header className="forge-topbar">
        <div className="topbar-left">
          <button className="shell-icon mobile-only" onClick={() => setMenuOpen(true)} aria-label="Open navigation"><Menu size={21}/></button>
          <form className="command-search" onSubmit={submit}>
            <Search size={18}/><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search opportunities, awards, vendors, agencies..."/><kbd><Command size={12}/> K</kbd>
          </form>
        </div>
        <div className="topbar-actions">
          <span className="live-source"><i/> Federal data workspace</span>
          <button className="user-chip" onClick={() => router.push("/account")}><span>{initials}</span><div><b>{displayName}</b><small>{session?.role}</small></div><ChevronDown size={14}/></button>
          <button className="toolbar-button" onClick={() => void logout()}>Sign out</button>
        </div>
      </header>
      <div className="forge-content">{children}</div>
    </main>
  </div>;
}
