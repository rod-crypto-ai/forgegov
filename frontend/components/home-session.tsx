"use client";
import dynamic from "next/dynamic";
import { useAuth } from "@/components/auth-provider";
const DashboardHome = dynamic(() => import("@/components/dashboard-home"));
export function HomeSession({ children }: { children: React.ReactNode }) {
  const { session } = useAuth();
  return session ? <DashboardHome/> : <>{children}</>;
}
