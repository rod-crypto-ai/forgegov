import Link from "next/link";
import { ArrowRight, Columns3 } from "lucide-react";
import { PageHeader } from "@/components/page-header";

const stages = ["Discovered", "Reviewing", "Qualified", "Bid / No-Bid", "Capture", "Proposal", "Submitted", "Awarded"];

export default function PipelinePage() {
  return (
    <>
      <PageHeader eyebrow="Capture management" title="Pipeline" description="A pursuit belongs here only after it has an owner, a next action, and a real decision path." actions={<Link className="primary-button" href="/opportunities">Add from search <ArrowRight size={16} /></Link>} />
      <section className="kanban-shell">
        {stages.map((stage) => (
          <div className="kanban-column" key={stage}>
            <div className="kanban-title"><span>{stage}</span><span>0</span></div>
            <div className="kanban-empty"><Columns3 size={22} /><p>No pursuits in this stage.</p></div>
          </div>
        ))}
      </section>
      <p className="helper-text">The API and database models for pipeline records are connected. The next milestone adds authenticated workspace creation and drag-and-drop stage updates.</p>
    </>
  );
}
