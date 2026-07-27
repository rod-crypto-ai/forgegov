"use client";

import { useEffect, useMemo, useState } from "react";
import { ArrowDownToLine, Columns3, LayoutList, Plus, RefreshCw, Search, X } from "lucide-react";
import { apiGet, apiPost, normalizeList } from "@/lib/api";
import type { NavItem } from "@/lib/navigation";

type Row = Record<string, unknown>;
type Field = { name: string; label: string; type?: "text" | "number" | "date" | "textarea"; required?: boolean };

const schemaByPath: Record<string, Field[]> = {
  "/capture/tasks": [
    { name: "title", label: "Task title", required: true },
    { name: "status", label: "Status" },
    { name: "due_at", label: "Due date", type: "date" },
  ],
  "/capture/saved-searches": [
    { name: "name", label: "Search name", required: true },
    { name: "query", label: "Search query", required: true },
  ],
  "/beacon/contacts": [
    { name: "full_name", label: "Full name", required: true },
    { name: "title", label: "Job title" },
    { name: "email", label: "Email" },
    { name: "phone", label: "Phone" },
    { name: "agency_name", label: "Agency / company" },
  ],
  "/capture/teaming": [
    { name: "company_name", label: "Company name", required: true },
    { name: "role", label: "Teaming role" },
    { name: "status", label: "Status" },
    { name: "capabilities", label: "Capabilities", type: "textarea" },
    { name: "notes", label: "Notes", type: "textarea" },
  ],
  "/capture/pursuits": [
    { name: "name", label: "Pursuit name", required: true },
    { name: "stage", label: "Stage" },
    { name: "estimated_value", label: "Estimated value", type: "number" },
    { name: "notes", label: "Capture notes", type: "textarea" },
  ],
};

const preferredKeys = ["title", "name", "full_name", "solicitation_number", "award_number", "agency", "agency_name", "recipient_name", "stage", "status", "due_at", "response_deadline", "estimated_value", "obligated_amount", "updated_at"];

function humanize(value: string) { return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase()); }
function display(value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return new Intl.NumberFormat("en-US", { maximumFractionDigits: 2 }).format(value);
  if (Array.isArray(value)) return value.join(", ") || "—";
  if (typeof value === "object") return "View details";
  const text = String(value);
  if (/^\d{4}-\d{2}-\d{2}T/.test(text)) return new Date(text).toLocaleString();
  return text;
}

function exportCsv(rows: Row[], columns: string[], name: string) {
  const quote = (value: unknown) => `"${String(display(value)).replaceAll('"', '""')}"`;
  const csv = [columns.map(quote).join(","), ...rows.map((row) => columns.map((column) => quote(row[column])).join(","))].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const anchor = document.createElement("a"); anchor.href = url; anchor.download = `${name}.csv`; anchor.click(); URL.revokeObjectURL(url);
}

export function WorkspacePage({ feature }: { feature: NavItem }) {
  const [rows, setRows] = useState<Row[]>([]);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [view, setView] = useState<"table" | "board">("table");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const fields = schemaByPath[feature.href] ?? [];

  async function load() {
    if (!feature.apiPath) { setRows([]); setStatus("ready"); return; }
    setStatus("loading"); setError("");
    try { setRows(normalizeList(await apiGet<Row[]>(feature.apiPath)) as Row[]); setStatus("ready"); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to load records"); setStatus("error"); }
  }
  useEffect(() => { void load(); }, [feature.href]);

  const columns = useMemo(() => {
    const keys = new Set(rows.flatMap(Object.keys));
    const selected = preferredKeys.filter((key) => keys.has(key)).slice(0, 7);
    return selected.length >= 2 ? selected : Array.from(keys).filter((key) => !["id", "raw_data", "description", "notes"].includes(key)).slice(0, 7);
  }, [rows]);
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? rows.filter((row) => Object.values(row).some((value) => String(display(value)).toLowerCase().includes(q))) : rows;
  }, [query, rows]);
  const boardGroups = useMemo(() => {
    const key = rows.some((row) => row.stage) ? "stage" : "status";
    return filtered.reduce<Record<string, Row[]>>((groups, row) => {
      const label = String(row[key] || "Unassigned"); (groups[label] ||= []).push(row); return groups;
    }, {});
  }, [filtered, rows]);

  async function createRecord(event: React.FormEvent) {
    event.preventDefault(); if (!feature.apiPath) return;
    setSaving(true); setError("");
    const payload = Object.fromEntries(Object.entries(form).map(([key, value]) => [key, value === "" ? null : value]));
    try { await apiPost(feature.apiPath.split("?")[0], payload); setCreateOpen(false); setForm({}); await load(); }
    catch (err) { setError(err instanceof Error ? err.message : "Record could not be created"); }
    finally { setSaving(false); }
  }

  return <>
    <header className="module-header">
      <div><span className="eyebrow">ForgeGov workspace</span><h1>{feature.label}</h1><p>{feature.description ?? `Manage ${feature.recordLabel ?? feature.label.toLowerCase()} intelligence, decisions, and team activity from one connected workspace.`}</p></div>
      <div className="module-actions">
        <button className="secondary-button" onClick={() => void load()}><RefreshCw size={16} /> Refresh</button>
        {fields.length > 0 && <button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={17} /> New {feature.recordLabel ?? "record"}</button>}
      </div>
    </header>

    <section className="workspace-summary">
      <div><span>Total</span><strong>{status === "ready" ? rows.length : "—"}</strong><small>Stored records</small></div>
      <div><span>Visible</span><strong>{status === "ready" ? filtered.length : "—"}</strong><small>Current result set</small></div>
      <div><span>Source</span><strong>{feature.apiPath ? "ForgeGov API" : "Configuration"}</strong><small>Traceable data</small></div>
      <div><span>Workspace status</span><strong className={status === "error" ? "status-bad" : "status-good"}>{status === "error" ? "Unavailable" : status === "loading" ? "Checking" : "Operational"}</strong><small>API-backed module</small></div>
    </section>

    <section className="data-panel workspace-panel">
      <div className="data-toolbar upgraded-toolbar">
        <div className="data-search"><Search size={17}/><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`Search ${feature.label.toLowerCase()}...`}/></div>
        <div className="segmented-control"><button className={view === "table" ? "active" : ""} onClick={() => setView("table")}><LayoutList size={16}/></button><button className={view === "board" ? "active" : ""} onClick={() => setView("board")}><Columns3 size={16}/></button></div>
        <button className="toolbar-button" onClick={() => exportCsv(filtered, columns, feature.label.toLowerCase().replaceAll(" ", "-"))} disabled={!filtered.length}><ArrowDownToLine size={16}/> Export</button>
      </div>

      {status === "loading" && <div className="table-state"><RefreshCw className="spin"/><strong>Loading workspace</strong><p>Retrieving the latest ForgeGov records.</p></div>}
      {status === "error" && <div className="table-state error-state"><strong>Workspace unavailable</strong><p>{error}</p><button className="secondary-button" onClick={() => void load()}>Try again</button></div>}
      {status === "ready" && !filtered.length && <div className="table-state"><strong>No records in this view</strong><p>Create the first record or adjust your search. This page is connected to the backend—not a placeholder.</p>{fields.length > 0 && <button className="primary-button" onClick={() => setCreateOpen(true)}><Plus size={16}/> Create record</button>}</div>}
      {status === "ready" && filtered.length > 0 && view === "table" && <div className="table-wrap"><table className="data-table"><thead><tr><th><input type="checkbox" aria-label="Select all"/></th>{columns.map((column) => <th key={column}>{humanize(column)}</th>)}</tr></thead><tbody>{filtered.map((row, index) => <tr key={String(row.id ?? index)}><td><input type="checkbox" aria-label="Select row"/></td>{columns.map((column, ci) => <td key={column} className={ci === 0 ? "primary-cell" : ""}>{display(row[column])}</td>)}</tr>)}</tbody></table></div>}
      {status === "ready" && filtered.length > 0 && view === "board" && <div className="kanban-board">{Object.entries(boardGroups).map(([group, items]) => <section className="kanban-column" key={group}><header><span>{humanize(group)}</span><b>{items.length}</b></header>{items.map((row, index) => <article className="kanban-card" key={String(row.id ?? index)}><strong>{String(row.title ?? row.name ?? row.full_name ?? "Untitled record")}</strong><p>{String(row.agency ?? row.agency_name ?? row.status ?? "ForgeGov record")}</p><footer><span>{display(row.estimated_value ?? row.due_at ?? row.updated_at)}</span></footer></article>)}</section>)}</div>}
    </section>

    {createOpen && <div className="modal-backdrop" onMouseDown={() => setCreateOpen(false)}><form className="record-modal" onSubmit={createRecord} onMouseDown={(e) => e.stopPropagation()}><header><div><span className="eyebrow">Create record</span><h2>New {feature.recordLabel ?? "record"}</h2></div><button type="button" className="icon-button" onClick={() => setCreateOpen(false)}><X size={20}/></button></header>{error && <div className="form-error">{error}</div>}<div className="record-form">{fields.map((field) => <label key={field.name}><span>{field.label}{field.required ? " *" : ""}</span>{field.type === "textarea" ? <textarea required={field.required} value={form[field.name] ?? ""} onChange={(e) => setForm({...form, [field.name]: e.target.value})}/> : <input type={field.type ?? "text"} required={field.required} value={form[field.name] ?? ""} onChange={(e) => setForm({...form, [field.name]: e.target.value})}/>}</label>)}</div><footer><button type="button" className="secondary-button" onClick={() => setCreateOpen(false)}>Cancel</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : "Create record"}</button></footer></form></div>}
  </>;
}
