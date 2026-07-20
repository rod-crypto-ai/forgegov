"use client";
import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type IntegrationStatus = { sam_gov?: { configured?: boolean } };
export function StatusBanner() {
  const [message, setMessage] = useState("Checking ForgeGov services...");
  const [ok, setOk] = useState(false);
  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/health/`).then((r) => { if (!r.ok) throw new Error(); return r.json(); }),
      fetch(`${API_BASE}/integrations/status/`).then((r) => r.json() as Promise<IntegrationStatus>),
    ]).then(([, integrations]) => {
      setOk(Boolean(integrations.sam_gov?.configured));
      setMessage(integrations.sam_gov?.configured ? "API connected · SAM.gov key configured" : "API connected · SAM.gov key still needs to be configured");
    }).catch(() => { setOk(false); setMessage("Backend is not running. Start the ForgeGov stack to connect live data."); });
  }, []);
  return <div className={`status-banner ${ok ? "success" : "warning"}`}>{message}</div>;
}
