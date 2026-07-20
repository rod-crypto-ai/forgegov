import { BarChart3 } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function AwardsPage() {
  return <><PageHeader eyebrow="USAspending" title="Awards intelligence" description="Analyze federal awards, incumbents, agencies, and contract history." /><section className="panel"><div className="empty-state"><BarChart3 size={30} /><strong>Award ingestion is not enabled yet</strong><p>The USAspending connector is present, but loading award data before the schema and aggregation rules are complete would create a bad dataset.</p></div></section></>;
}
