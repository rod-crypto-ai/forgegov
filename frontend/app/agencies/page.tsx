import { Building2 } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function AgenciesPage() {
  return <><PageHeader eyebrow="Market intelligence" title="Agencies" description="Track buying behavior, notices, spending, incumbents, and expiring contracts by agency." /><section className="panel"><div className="empty-state"><Building2 size={30} /><strong>Agency profiles require award ingestion</strong><p>This route is ready; profiles will activate after USAspending records are normalized.</p></div></section></>;
}
