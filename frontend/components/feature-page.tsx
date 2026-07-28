"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, RefreshCw, Search } from "lucide-react";
import { apiGet, normalizeList } from "@/lib/api";
import type { NavItem } from "@/lib/navigation";

const preferredKeys = [
  "title",
  "name",
  "full_name",
  "award_number",
  "solicitation_number",
  "agency",
  "awarding_agency",
  "recipient_name",
  "company_name",
  "code",
  "category_type",
  "stage",
  "status",
  "due_at",
  "response_deadline",
  "estimated_value",
  "obligated_amount",
  "updated_at",
];

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

function displayValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
  if (typeof value === "object") return "View details";
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return new Date(text).toLocaleString();
  return text;
}

function downloadCsv(rows: Array<Record<string, unknown>>, columns: string[], fileName: string) {
  const escape = (value: unknown) => `"${String(displayValue(value)).replaceAll('"', '""')}"`;
  const csv = [columns.map(escape).join(","), ...rows.map((row) => columns.map((column) => escape(row[column])).join(","))].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = fileName;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function FeaturePage({ feature }: { feature: NavItem }) {
  const [rows, setRows] = useState<Array<Record<string, unknown>>>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  async function load() {
    if (!feature.apiPath) {
      setRows([]);
      setStatus("ready");
      return;
    }
    setStatus("loading");
    setError("");
    try {
      const payload = await apiGet<unknown>(feature.apiPath);
      const objectPayload = payload as Record<string, unknown>;
      const liveRows = Array.isArray(objectPayload?.results) ? objectPayload.results : Array.isArray(objectPayload?.opportunities) ? objectPayload.opportunities : normalizeList(payload as never);
      setRows(liveRows as Array<Record<string, unknown>>);
      setLastUpdated(new Date());
      setStatus("ready");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "The data source could not be loaded.");
      setStatus("error");
    }
  }

  useEffect(() => {
    // Loading a new route is the external synchronization performed by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [feature.href]);

  const columns = useMemo(() => {
    if (feature.columns?.length) return feature.columns.map((column) => column.key);
    const keys = new Set(rows.flatMap((row) => Object.keys(row)));
    const selected = preferredKeys.filter((key) => keys.has(key)).slice(0, 6);
    if (selected.length >= 3) return selected;
    return Array.from(keys).filter((key) => !["id", "raw_data", "description", "notes"].includes(key)).slice(0, 6);
  }, [feature.columns, rows]);

  const filteredRows = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return rows;
    return rows.filter((row) => Object.values(row).some((value) => String(displayValue(value)).toLowerCase().includes(normalized)));
  }, [query, rows]);

  const description = feature.description ?? `Search, filter, review, and export ${feature.recordLabel ?? feature.label.toLowerCase()} records in one workspace.`;

  return (
    <>
      <div className="feature-hero">
        <div>
          <span className="eyebrow">ForgeGov intelligence</span>
          <h1>{feature.label}</h1>
          <p>{description}</p>
        </div>
        <div className="feature-actions">
          <button className="secondary-button" type="button" onClick={() => void load()} disabled={status === "loading"}>
            <RefreshCw size={16} className={status === "loading" ? "spin" : ""} /> Refresh
          </button>
        </div>
      </div>

      <section className="insight-strip">
        <div><span>Total records</span><strong>{status === "ready" ? rows.length : "—"}</strong></div>
        <div><span>Visible results</span><strong>{status === "ready" ? filteredRows.length : "—"}</strong></div>
        <div><span>Data source</span><strong>{feature.apiPath ? "ForgeGov API" : "Configuration"}</strong></div>
        <div><span>Last refreshed</span><strong>{lastUpdated ? lastUpdated.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "Not loaded"}</strong></div>
      </section>

      <section className="data-panel">
        <div className="data-toolbar">
          <div className="data-search"><Search size={17} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${feature.label.toLowerCase()}...`} /></div>
          <button className="toolbar-button" onClick={() => downloadCsv(filteredRows, columns, `${feature.label.toLowerCase().replaceAll(" ", "-")}.csv`)} disabled={!filteredRows.length}>
            <ArrowDownToLine size={16} /> Export
          </button>
        </div>

        {status === "loading" && <div className="table-state"><RefreshCw className="spin" /><strong>Loading live workspace data</strong><p>ForgeGov is requesting the latest records from the backend.</p></div>}
        {status === "error" && <div className="table-state error-state"><strong>Backend data is unavailable</strong><p>{error}</p><button className="secondary-button" onClick={() => void load()}>Try again</button></div>}
        {status === "ready" && !filteredRows.length && (
          <div className="table-state"><strong>No matching records yet</strong><p>This module is connected, but the database does not contain records matching the current view. Records can be created through the Django admin or REST API until the module-specific form is added.</p></div>
        )}
        {status === "ready" && filteredRows.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead><tr>{columns.map((column) => <th key={column}>{humanize(column)}</th>)}</tr></thead>
              <tbody>
                {filteredRows.map((row, index) => (
                  <tr key={String(row.id ?? `${feature.href}-${index}`)}>
                    {columns.map((column, columnIndex) => <td key={column} className={columnIndex === 0 ? "primary-cell" : ""}>{displayValue(row[column])}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
