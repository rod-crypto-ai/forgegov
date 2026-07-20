"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  BarChart3,
  Bell,
  Building2,
  ChevronDown,
  FileText,
  FolderKanban,
  Handshake,
  LayoutDashboard,
  Menu,
  Search,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";

const sections = [
  {
    label: "Capture",
    items: [
      { href: "/", label: "Dashboard", icon: LayoutDashboard },
      { href: "/pipeline", label: "Pipeline", icon: FolderKanban },
      { href: "/tasks", label: "Tasks", icon: FileText },
      { href: "/team", label: "Team", icon: Users },
      { href: "/teaming", label: "Teaming", icon: Handshake },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/opportunities", label: "Opportunities", icon: Search },
      { href: "/awards", label: "Awards", icon: BarChart3 },
      { href: "/agencies", label: "Agencies", icon: Building2 },
      { href: "/files", label: "Files", icon: FileText },
    ],
  },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${open ? "sidebar-open" : ""}`}>
        <div className="brand-row">
          <Link href="/" className="brand" onClick={() => setOpen(false)}>
            <span className="brand-mark">FG</span>
            <span>ForgeGov</span>
          </Link>
          <button className="icon-button mobile-only" aria-label="Close menu" onClick={() => setOpen(false)}><X size={20} /></button>
        </div>

        <Link className="ai-button" href="/assistant" onClick={() => setOpen(false)}>
          <Sparkles size={18} /> AI Assistant
        </Link>

        <nav>
          {sections.map((section) => (
            <div className="nav-section" key={section.label}>
              <div className="nav-heading">{section.label}<ChevronDown size={14} /></div>
              {section.items.map((item) => {
                const active = pathname === item.href;
                const Icon = item.icon;
                return (
                  <Link key={item.href} href={item.href} onClick={() => setOpen(false)} className={`nav-link ${active ? "active" : ""}`}>
                    <Icon size={18} /> {item.label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <Link href="/settings" className={`nav-link ${pathname === "/settings" ? "active" : ""}`} onClick={() => setOpen(false)}>
            <Settings size={18} /> Settings
          </Link>
          <div className="account-card">
            <div className="avatar">RH</div>
            <div><strong>Workspace</strong><span>Development mode</span></div>
          </div>
        </div>
      </aside>

      {open && <button className="backdrop" aria-label="Close menu" onClick={() => setOpen(false)} />}

      <main className="main-area">
        <header className="topbar">
          <button className="icon-button mobile-only" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={22} /></button>
          <div className="global-search"><Search size={18} /><input aria-label="Global search" placeholder="Search opportunities, awards, agencies..." /></div>
          <button className="icon-button" aria-label="Notifications"><Bell size={20} /></button>
        </header>
        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}
