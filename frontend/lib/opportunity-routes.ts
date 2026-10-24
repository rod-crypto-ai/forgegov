type OpportunitySource = { source_id?: string; source?: string };

export function opportunityHref(opportunity: OpportunitySource): string {
  const sourceId = String(opportunity.source_id ?? "");
  if (opportunity.source === "grants.gov" || sourceId.startsWith("grants.gov:")) {
    const id = sourceId.replace(/^grants\.gov:/, "");
    return id ? `/opportunities/federal-grants/${encodeURIComponent(id)}` : "/opportunities/federal-grants";
  }
  if (opportunity.source === "sba-subnet" || sourceId.startsWith("sba-subnet:")) {
    return sourceId ? `/opportunities/subcontracting/${encodeURIComponent(sourceId)}` : "/opportunities/subcontracting";
  }
  return sourceId ? `/opportunities/federal-contracts/${encodeURIComponent(sourceId)}` : "/opportunities/federal-contracts";
}
