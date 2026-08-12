"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { authFetch } from "@/lib/api";

type Session = {
  user: { id: number; email: string; first_name: string; last_name: string };
  organization: { id: number; name: string; slug: string };
  role: string;
};

type WorkspaceMembership={organization:{id:number;name:string;slug:string};role:string;job_title?:string};

type AuthContextValue = {
  session: Session | null;
  workspaces: WorkspaceMembership[];
  loading: boolean;
  reload: () => Promise<void>;
  switchWorkspace: (organizationId:number) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);
const publicPaths = ["/sign-in", "/register", "/forgot-password", "/reset-password", "/verify-email", "/terms", "/privacy"];

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [workspaces, setWorkspaces] = useState<WorkspaceMembership[]>([]);
  const pathname = usePathname();
  const router = useRouter();

  const reload = useCallback(async () => {
    try {
      const [data, workspaceData] = await Promise.all([
        authFetch<Session>("/auth/me/"),
        authFetch<{workspaces:WorkspaceMembership[]}>("/auth/workspaces/"),
      ]);
      setSession(data);
      setWorkspaces(workspaceData.workspaces??[]);
    } catch {
      setSession(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => void reload(), 0);
    return () => window.clearTimeout(timer);
  }, [reload]);

  useEffect(() => {
    if (!loading && !session && !publicPaths.some((path) => pathname.startsWith(path))) {
      router.replace(`/sign-in?next=${encodeURIComponent(pathname)}`);
    }
    if (!loading && session && (pathname === "/sign-in" || pathname === "/register")) {
      router.replace("/");
    }
  }, [loading, session, pathname, router]);


  const switchWorkspace = useCallback(async (organizationId:number) => {
    await authFetch("/auth/workspaces/", { method: "POST", body: JSON.stringify({ organization: organizationId }) });
    await reload();
    router.refresh();
  }, [reload, router]);

  const logout = useCallback(async () => {
    try { await authFetch("/auth/logout/", { method: "POST" }); } catch {}
    setSession(null);
    router.replace("/sign-in");
  }, [router]);

  const value = useMemo(() => ({ session, workspaces, loading, reload, switchWorkspace, logout }), [session, workspaces, loading, reload, switchWorkspace, logout]);

  if (loading && !publicPaths.some((path) => pathname.startsWith(path))) {
    return <div className="auth-loading"><div className="auth-spinner" /><p>Securing your ForgeGov workspace…</p></div>;
  }
  if (!session && !publicPaths.some((path) => pathname.startsWith(path))) return null;
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
