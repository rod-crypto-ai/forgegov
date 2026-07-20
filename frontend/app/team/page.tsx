import { Users } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function TeamPage() {
  return (
    <>
      <PageHeader eyebrow="Workspace" title="Team and permissions" description="Invite members and control who can view, edit, approve, or administer capture work." />
      <section className="panel"><div className="empty-state"><Users size={30} /><strong>No workspace members loaded</strong><p>Organization and membership models are active. Invitation and onboarding workflows are the next build item.</p></div></section>
    </>
  );
}
