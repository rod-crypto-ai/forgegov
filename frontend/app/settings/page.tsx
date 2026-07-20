import { PageHeader } from "@/components/page-header";

export default function SettingsPage() {
  return (
    <><PageHeader eyebrow="Configuration" title="Settings" description="Control workspace identity, data integrations, permissions, and notification policies." /><section className="panel settings-grid"><div><label>Application API</label><input readOnly value={process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api"} /></div><div><label>SAM.gov credential</label><input readOnly value="Stored server-side through SAM_GOV_API_KEY" /></div><div><label>USAspending</label><input readOnly value="Public API connector configured" /></div></section></>
  );
}
