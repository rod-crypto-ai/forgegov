"use client";

import { useCallback, useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { authFetch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

type Log = { id: number; action: string; object_type: string; object_id: string; actor_name: string; created_at: string };
export default function AuditLogPage() {
  const { session } = useAuth();
  const [rows, setRows] = useState<Log[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const admin = ["owner", "admin"].includes(session?.role || "");
  const load = useCallback(async () => {
    if (!admin) return;
    setLoading(true); setError("");
    try { setRows(await authFetch<Log[]>("/audit-logs/")); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Audit log could not be loaded."); }
    finally { setLoading(false); }
  }, [admin]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 0); return () => window.clearTimeout(timer); }, [load]);
  const filtered = rows.filter(row => `${row.action} ${row.actor_name} ${row.object_type} ${row.object_id}`.toLowerCase().includes(query.toLowerCase()));
  const pages = Math.max(1, Math.ceil(filtered.length / 25));
  const currentPage = Math.min(page, pages);
  return <div className="page-stack"><header className="feature-hero"><div><span className="eyebrow">Security</span><h1>Audit log</h1><p>Review account, team, and workspace activity. This view includes the latest 250 workspace events.</p></div>{admin && <button className="secondary-button" disabled={loading} onClick={() => void load()}><RefreshCw size={16}/>Refresh events</button>}</header>
    <section className="data-panel">{!admin ? <p>Only owners and administrators can view audit logs.</p> : <>
      <label className="audit-log-search"><span>Filter loaded events</span><input type="search" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} placeholder="Action, actor, or record"/></label>
      {error ? <div className="system-banner warning" role="alert">{error}</div> : loading ? <div className="table-state" role="status"><RefreshCw className="spin"/><strong>Loading audit events…</strong></div> : !filtered.length ? <div className="table-state"><strong>No matching audit events</strong><p>{query ? "Try another filter." : "Recorded account and workspace activity will appear here."}</p></div> : <div className="simple-table">{filtered.slice((currentPage - 1) * 25, currentPage * 25).map(row => <div className="simple-row" key={row.id}><span><b>{row.action}</b><small>{row.actor_name || "System"} · {row.object_type} {row.object_id}</small></span><time dateTime={row.created_at}>{new Date(row.created_at).toLocaleString()}</time></div>)}</div>}
      {!loading && !error && filtered.length > 25 && <nav className="pagination-bar" aria-label="Audit event pages"><button className="secondary-button" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</button><span>Page {currentPage} of {pages} · {filtered.length} loaded events</span><button className="secondary-button" disabled={currentPage >= pages} onClick={() => setPage(currentPage + 1)}>Next</button></nav>}
    </>}</section></div>;
}
