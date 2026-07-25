"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, BarChart3, Building2, CircleDollarSign, TrendingUp, Users } from "lucide-react";
import { apiGet } from "@/lib/api";

type Summary = {
  opportunities?: { total?: number; active?: number };
  awards?: { total?: number; obligated_total?: number };
  vendors?: number;
  pipeline?: { total?: number; weighted_value?: number; by_stage?: Record<string, number> };
};


function exportSummary(title: string, summary: Summary) {
  const rows = [
    ["Metric", "Value"],
    ["Active notices", summary.opportunities?.active ?? 0],
    ["Awards loaded", summary.awards?.total ?? 0],
    ["Vendors tracked", summary.vendors ?? 0],
    ["Pipeline records", summary.pipeline?.total ?? 0],
    ["Weighted pipeline", summary.pipeline?.weighted_value ?? 0],
  ];
  const csv = rows.map((row) => row.map((value) => `"${String(value).replaceAll('"', '""')}"`).join(",")).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${title.toLowerCase().replaceAll(" ", "-")}.csv`;
  anchor.click();
  URL.revokeObjectURL(url);
}
export function ReportPage({ type }: { type: "funding" | "new-entrants" }) {
  const [summary, setSummary] = useState<Summary>({});
  const [error, setError] = useState("");
  useEffect(() => { apiGet<Summary>("/dashboard/summary/").then(setSummary).catch((reason) => setError(String(reason))); }, []);

  const stageRows = useMemo(() => Object.entries(summary.pipeline?.by_stage ?? {}), [summary]);
  const title = type === "funding" ? "Funding Intelligence" : "New Entrants";
  const description = type === "funding"
    ? "Analyze real award, pipeline, and agency funding records without presenting invented market totals."
    : "Identify organizations appearing in agencies and markets for the first time after vendor and award ingestion is active.";

  return (
    <>
      <div className="feature-hero"><div><span className="eyebrow">Market intelligence reports</span><h1>{title}</h1><p>{description}</p></div><div className="feature-actions"><button className="primary-button" onClick={() => exportSummary(title, summary)}><ArrowDownToLine size={16} /> Export report</button></div></div>
      {error && <div className="system-banner warning">The reporting API is unavailable: {error}</div>}
      <div className="report-metrics">
        <div><span className="report-icon"><CircleDollarSign size={20} /></span><p>Weighted pipeline</p><strong>${Number(summary.pipeline?.weighted_value ?? 0).toLocaleString()}</strong><small>Estimated value × pWin</small></div>
        <div><span className="report-icon"><BarChart3 size={20} /></span><p>Awards loaded</p><strong>{summary.awards?.total ?? 0}</strong><small>Stored award records</small></div>
        <div><span className="report-icon"><Building2 size={20} /></span><p>Active notices</p><strong>{summary.opportunities?.active ?? 0}</strong><small>SAM.gov records marked active</small></div>
        <div><span className="report-icon"><Users size={20} /></span><p>Vendors tracked</p><strong>{summary.vendors ?? 0}</strong><small>Vendor intelligence profiles</small></div>
      </div>
      <div className="two-column report-grid">
        <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">Distribution</span><h2>Pipeline stage mix</h2></div><TrendingUp size={22} /></div>
          {!stageRows.length ? <div className="table-state compact-state"><strong>No reportable pipeline data</strong><p>Add pursuits to generate a real stage distribution.</p></div> : <div className="bar-list">{stageRows.map(([stage, count]) => <div key={stage}><span>{stage.replaceAll("_", " ")}</span><div><i style={{ width: `${Math.max((count / Math.max(summary.pipeline?.total ?? 1, 1)) * 100, 5)}%` }} /></div><b>{count}</b></div>)}</div>}
        </section>
        <section className="data-panel"><div className="panel-title-row"><div><span className="eyebrow">Data requirement</span><h2>{type === "funding" ? "Funding source coverage" : "Entrant detection status"}</h2></div></div>
          <div className="coverage-list"><div><span className="status-dot live" /><div><strong>Workspace pipeline</strong><small>Connected</small></div></div><div><span className="status-dot pending" /><div><strong>USAspending award ingestion</strong><small>Connector expansion required</small></div></div><div><span className="status-dot pending" /><div><strong>State and local awards</strong><small>Source licensing and connectors required</small></div></div></div>
        </section>
      </div>
    </>
  );
}
