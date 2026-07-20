import { FileText } from "lucide-react";
import { PageHeader } from "@/components/page-header";

export default function FilesPage() {
  return <><PageHeader eyebrow="Documents" title="Files" description="Store solicitation attachments, amendments, capability statements, and proposal files with source history." /><section className="panel"><div className="empty-state"><FileText size={30} /><strong>Object storage is not configured</strong><p>File uploads will not be faked with browser-only storage. Secure S3-compatible storage comes with the authenticated MVP.</p></div></section></>;
}
