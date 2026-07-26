"use client";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type IntegrationStatus = { sam_gov?: { configured?: boolean } };
export function StatusBanner() {
  const [message, setMessage] = useState("Checking ForgeGov services...");
  const [ok, setOk] = useState(false);
  useEffect(() => {
    Promise.all([
      apiGet<{ status: string }>("/health/"),
      apiGet<IntegrationStatus>("/integrations/status/"),
    ]).then(([, integrations]) => {
      setOk(Boolean(integrations.sam_gov?.configured));
      setMessage(integrations.sam_gov?.configured ? "API connected · SAM.gov key configured" : "API connected · SAM.gov key still needs to be configured");
    }).catch((error) => {
      setOk(false);
      setMessage(error instanceof Error ? error.message : "ForgeGov services could not be reached.");
    });
  }, []);
  return <div className={`status-banner ${ok ? "success" : "warning"}`}>{message}</div>;
}
