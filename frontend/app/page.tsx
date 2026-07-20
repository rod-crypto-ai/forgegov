import Link from "next/link";
import { ArrowRight, CalendarClock, CircleDollarSign, Search, Target, Users } from "lucide-react";
import { PageHeader } from "@/components/page-header";
import { StatusBanner } from "@/components/status-banner";

const cards = [
  { label: "Live opportunity search", value: "SAM.gov", detail: "Search current federal notices", href: "/opportunities", icon: Search },
  { label: "Active pursuits", value: "Pipeline", detail: "Qualify, capture, submit, and track", href: "/pipeline", icon: Target },
  { label: "Upcoming work", value: "Tasks", detail: "Assigned deadlines and next actions", href: "/tasks", icon: CalendarClock },
  { label: "Workspace", value: "Team", detail: "Members, roles, and collaboration", href: "/team", icon: Users },
];

export default function DashboardPage() {
  return (
    <>
      <PageHeader eyebrow="Command center" title="Government contracting dashboard" description="Move from opportunity discovery to a disciplined capture decision without losing deadlines, documents, or accountability." />
      <StatusBanner />

      <div className="metric-grid">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Link className="metric-card" href={card.href} key={card.href}>
              <div className="metric-icon"><Icon size={20} /></div>
              <span>{card.label}</span>
              <strong>{card.value}</strong>
              <p>{card.detail}</p>
              <div className="card-link">Open <ArrowRight size={16} /></div>
            </Link>
          );
        })}
      </div>

      <div className="two-column">
        <section className="panel">
          <div className="panel-header"><div><span className="eyebrow">Get operational</span><h2>Required setup</h2></div></div>
          <div className="checklist">
            <div><span className="check-index">1</span><div><strong>Start the application stack</strong><p>Run Docker Compose so the frontend, API, database, Redis, and workers are connected.</p></div></div>
            <div><span className="check-index">2</span><div><strong>Add the SAM.gov API key</strong><p>Live federal opportunity search will reject requests until the key is configured securely.</p></div></div>
            <div><span className="check-index">3</span><div><strong>Create the first workspace</strong><p>Add your company profile before opportunity recommendations are scored.</p></div></div>
          </div>
        </section>

        <section className="panel dark-panel">
          <CircleDollarSign size={28} />
          <span className="eyebrow">Product discipline</span>
          <h2>Do not build decorative dashboards.</h2>
          <p>Every number must come from a government source or an authenticated workspace record. Fake metrics make the product look finished while hiding that it does nothing.</p>
          <Link href="/opportunities" className="primary-button">Search live opportunities <ArrowRight size={17} /></Link>
        </section>
      </div>
    </>
  );
}
              <span>{card.label}</span><strong>{card.value}</strong><p>{card.detail}</p><div className="card-link">Open <ArrowRight size={16} /></div>
            </Link>
          );
        })}
      </div>
      <div className="two-column">
        <section className="panel"><span className="eyebrow">Next build milestone</span><h2>Turn live notices into pursuits</h2><p className="helper-text">Search SAM.gov, persist the returned records, then qualify selected opportunities into a company pipeline.</p><Link href="/opportunities" className="primary-button"><Search size={17}/> Search opportunities</Link></section>
        <section className="panel dark-panel"><CircleDollarSign size={28}/><span className="eyebrow">Data discipline</span><h2>No fake metrics.</h2><p>Every number above comes from the ForgeGov database. Empty means the platform has not ingested or created the record yet.</p></section>
      </div>
    </>
  );
}
