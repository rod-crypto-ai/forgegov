"use client";

import { useAuth } from "@/components/auth-provider";
import DashboardHome from "@/components/dashboard-home";
import { PublicLanding } from "@/components/public-landing";

export default function HomePage() {
  const { session, loading } = useAuth();
  if (loading) return <div className="landing-loading">Loading ForgeGov…</div>;
  return session ? <DashboardHome /> : <PublicLanding />;
}
