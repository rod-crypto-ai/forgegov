"use client";

import { useEffect, useMemo, useState } from "react";
import { Activity, CheckCircle2, ExternalLink, KeyRound, RefreshCw, ServerCog, TriangleAlert } from "lucide-react";
import { apiGet } from "@/lib/api";

type Connector = {
  key: string;
  name: string;
  label?: string;
  scope: string;
  jurisdiction_code: string;
  jurisdiction_name: string;
  configured: boolean | null;
  reachable: boolean | null;
  status: string;
  detail: string;
  official_url: string;
  authentication: string;
  documentation_url?: string;
  license_name?: string;
  license_url?: string;
  capabilities?: string[];
  rate_limit?: string;
  last_sync_at?: string | null;
  record_count?: number;
};

type Payload = {
  connectors: Connector[];
  summary: { total: number; healthy: number; attention?: number; enabled?: number };
};

const empty: Payload = { connectors: [], summary: { total: 0, healthy: 0, attention: 0 } };

export default function ConnectorManagerPage() {
  const [data, setData] = useState<Payload>(empty);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function load(probe = false) {
    setLoading(true);
    setError("");
    try {
      setData(await apiGet<Payload>(`/intelligence/connector-registry/${probe ? "?probe=true" : ""}`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Connector status could not be loaded.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void load(false), 0);
    return () => window.clearTimeout(timer);
  }, []);

  const healthyPercent = useMemo(() => data.summary.total ? Math.round((data.summary.healthy / data.summary.total) * 100) : 0, [data]);

  return <div className="page-stack connector-manager-page">
    <section className="page-hero connector-hero">
      <div>
        <span className="eyebrow">INTELLIGENCE FOUNDATION</span>
        <h1>Connector Manager</h1>
        <p>See which official data sources are ready, which require credentials, and what ForgeGov can safely use for evidence-backed intelligence.</p>
      </div>
      <button className="button solid" onClick={() => void load(true)} disabled={loading}><RefreshCw size={17}/>{loading ? "Checking…" : "Probe connectors"}</button>
    </section>

    {error && <div className="system-banner warning"><TriangleAlert size={18}/><span>{error}</span></div>}

    <section className="connector-summary-grid">
      <article><ServerCog/><span><small>Total connectors</small><strong>{data.summary.total}</strong></span></article>
      <article><CheckCircle2/><span><small>Healthy</small><strong>{data.summary.healthy}</strong></span></article>
      <article><TriangleAlert/><span><small>Needs attention</small><strong>{data.summary.attention}</strong></span></article>
      <article><Activity/><span><small>Foundation health</small><strong>{healthyPercent}%</strong></span></article>
    </section>

    <section className="connector-grid">
      {data.connectors.map(row => <article className={`connector-card status-${row.status}`} key={row.key}>
        <header><span className="connector-icon"><ServerCog/></span><div><h2>{row.name || row.label}</h2><p>{row.detail || "Connector metadata registered."}</p></div><span className="connector-status"><i/>{row.status.replaceAll("_", " ")}</span></header>
        <dl>
          <div><dt>Scope</dt><dd>{row.scope}{row.jurisdiction_name ? ` · ${row.jurisdiction_name}` : ""}</dd></div>
          <div><dt>Configuration</dt><dd>{row.configured === null ? "Not probed" : row.configured ? "Configured" : "Required"}</dd></div>
          <div><dt>Reachability</dt><dd>{row.reachable === null ? "Not probed" : row.reachable ? "Reachable" : "Unavailable"}</dd></div>
          <div><dt>Authentication</dt><dd><KeyRound size={14}/>{row.authentication}</dd></div>
          <div><dt>License</dt><dd>{row.license_name || "Review required"}</dd></div>
          <div><dt>Coverage</dt><dd>{row.capabilities?.join(", ") || "Metadata only"}</dd></div>
          <div><dt>Stored records</dt><dd>{(row.record_count || 0).toLocaleString()}</dd></div>
        </dl>
        <a href={row.official_url} target="_blank" rel="noreferrer">Open official source <ExternalLink size={14}/></a>
      </article>)}
      {!loading && data.connectors.length === 0 && <div className="empty-state"><ServerCog size={32}/><h2>No connectors were returned.</h2><p>Check the ForgeGov backend and integration settings.</p></div>}
    </section>

    <section className="evidence-standard-panel">
      <div><span className="eyebrow">TRUST STANDARD</span><h2>Official data and AI inference stay separate.</h2></div>
      <p>Every v2.7 intelligence response carries a source classification, confidence level, timestamp, and evidence. Likely competitors are never presented as confirmed bidders.</p>
    </section>
  </div>;
}
