import { CheckCircle2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function TasksPage() {
  return (
    <>
      <PageHeader eyebrow="Execution" title="Tasks" description="Track the work that determines whether a pursuit advances or dies." />
      <section className="panel"><div className="empty-state"><CheckCircle2 size={30} /><strong>No tasks yet</strong><p>Tasks will appear after a workspace and pursuit are created through the API.</p></div></section>
    </>
  );
}
