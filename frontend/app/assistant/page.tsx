import { Sparkles } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function AssistantPage() {
  return <><PageHeader eyebrow="Grounded AI" title="Contracting assistant" description="Analyze solicitations and capture records with citations to the original source." /><section className="panel"><div className="empty-state"><Sparkles size={30} /><strong>AI is deliberately locked</strong><p>It will be enabled only after document ingestion and citation tracking work. A chat box that invents requirements would damage the product.</p></div></section></>;
}
