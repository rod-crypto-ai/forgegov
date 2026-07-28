"use client";

import { Suspense } from "react";
import { notFound, usePathname } from "next/navigation";
import { AssistantWorkspace } from "@/components/assistant-workspace";
import { WorkspacePage } from "@/components/workspace-page";
import { OpportunityExplorer, type OpportunityMode } from "@/components/opportunity-explorer";
import { ReportPage } from "@/components/report-page";
import { AwardIntelligence } from "@/components/award-intelligence";
import { getFeatureByPath } from "@/lib/navigation";
import { PipelineWorkspace, PursuitsWorkspace, TasksWorkspace, SavedSearchesWorkspace } from "@/components/capture-workspaces";
import { AlertsWorkspace, ContractVehicleWorkspace, ForecastWorkspace, MarketAnalyticsWorkspace, ProfileWorkspace, StateLocalWorkspace, SubcontractWorkspace, TeamingWorkspace } from "@/components/expansion-workspaces";

export default function DynamicFeaturePage() {
  const pathname = usePathname();
  const feature = getFeatureByPath(pathname);
  if (!feature) return notFound();

  if (pathname === "/assistant") return <AssistantWorkspace />;
  if (pathname === "/reports/funding") return <ReportPage type="funding" />;
  if (pathname === "/reports/new-entrants") return <ReportPage type="new-entrants" />;
  if (pathname === "/awards/federal-contracts") return <AwardIntelligence />;
  if (pathname === "/capture/teaming") return <TeamingWorkspace />;
  if (pathname === "/capture/pipelines") return <PipelineWorkspace />;
  if (pathname === "/capture/pursuits") return <PursuitsWorkspace />;
  if (pathname === "/capture/tasks") return <TasksWorkspace />;
  if (pathname === "/capture/saved-searches") return <SavedSearchesWorkspace />;
  if (pathname === "/capture/alerts") return <AlertsWorkspace />;
  if (pathname === "/opportunities/federal-forecasts") return <ForecastWorkspace />;
  if (pathname === "/opportunities/federal-vehicles") return <ContractVehicleWorkspace />;
  if (pathname === "/opportunities/state-local") return <StateLocalWorkspace />;
  if (pathname === "/opportunities/subcontracting") return <SubcontractWorkspace />;
  if (pathname === "/participants/federal-agencies") return <ProfileWorkspace kind="agency" />;
  if (pathname === "/participants/vendors") return <ProfileWorkspace kind="vendor" />;
  if (pathname === "/categories/naics") return <MarketAnalyticsWorkspace categoryType="naics" />;
  if (pathname === "/categories/psc") return <MarketAnalyticsWorkspace categoryType="psc" />;
  if (pathname.startsWith("/opportunities/")) {
    return <Suspense fallback={<div className="table-state"><strong>Loading opportunity search…</strong></div>}><OpportunityExplorer mode={pathname.split("/").at(-1) as OpportunityMode} /></Suspense>;
  }
  return <WorkspacePage feature={feature} />;
}
