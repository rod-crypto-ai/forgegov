"use client";
import dynamic from "next/dynamic";
import { useAuth } from "@/components/auth-provider";
import { useHydrated } from "@/lib/use-hydrated";
const DashboardHome = dynamic(() => import("@/components/dashboard-home"));
export function HomeSession({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  const hydrated = useHydrated();
  return hydrated && session ? <DashboardHome/> : <>{children}</>;
}
