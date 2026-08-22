"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiGet, apiPatch } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

export type ThemePreference = "system" | "light" | "dark";
export type DensityPreference = "comfortable" | "compact";
export type AIResponseStyle = "concise" | "balanced" | "detailed";

export type UserPreferences = {
  theme: ThemePreference;
  density: DensityPreference;
  reduce_motion: boolean;
  sidebar_collapsed: boolean;
  ai_response_style: AIResponseStyle;
  ai_live_web_enabled: boolean;
  ai_workspace_grounding_enabled: boolean;
  updated_at?: string;
};

const defaults: UserPreferences = {
  theme: "system",
  density: "comfortable",
  reduce_motion: false,
  sidebar_collapsed: false,
  ai_response_style: "balanced",
  ai_live_web_enabled: true,
  ai_workspace_grounding_enabled: true,
};

const storageKey = "forgegov-ui-preferences";

type ThemeContextValue = {
  preferences: UserPreferences;
  resolvedTheme: "light" | "dark";
  loaded: boolean;
  updatePreferences: (patch: Partial<UserPreferences>, persist?: boolean) => Promise<void>;
  reloadPreferences: () => Promise<void>;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function readLocal(): UserPreferences {
  if (typeof window === "undefined") return defaults;
  try {
    const parsed = JSON.parse(window.localStorage.getItem(storageKey) || "{}");
    return { ...defaults, ...parsed };
  } catch {
    return defaults;
  }
}

function resolveTheme(theme: ThemePreference): "light" | "dark" {
  if (theme === "light" || theme === "dark") return theme;
  if (typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches) return "dark";
  return "light";
}

function applyToDocument(preferences: UserPreferences) {
  if (typeof document === "undefined") return;
  const resolved = resolveTheme(preferences.theme);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preferences.theme;
  document.documentElement.dataset.density = preferences.density;
  document.documentElement.dataset.reduceMotion = preferences.reduce_motion ? "true" : "false";
  document.documentElement.style.colorScheme = resolved;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const [preferences, setPreferences] = useState<UserPreferences>(() => readLocal());
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(() => resolveTheme(readLocal().theme));
  const [loaded, setLoaded] = useState(false);

  const apply = useCallback((next: UserPreferences) => {
    setPreferences(next);
    setResolvedTheme(resolveTheme(next.theme));
    if (typeof window !== "undefined") window.localStorage.setItem(storageKey, JSON.stringify(next));
    applyToDocument(next);
  }, []);

  const reloadPreferences = useCallback(async () => {
    if (!session) {
      const local = readLocal();
      apply(local);
      setLoaded(true);
      return;
    }
    try {
      const remote = await apiGet<UserPreferences>("/settings/preferences/");
      apply({ ...defaults, ...remote });
    } catch {
      apply(readLocal());
    } finally {
      setLoaded(true);
    }
  }, [apply, session]);

  useEffect(() => {
    const timer = window.setTimeout(() => void reloadPreferences(), 0);
    return () => window.clearTimeout(timer);
  }, [reloadPreferences]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if (preferences.theme === "system") {
        const resolved = resolveTheme("system");
        setResolvedTheme(resolved);
        document.documentElement.dataset.theme = resolved;
        document.documentElement.style.colorScheme = resolved;
      }
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [preferences.theme]);

  const updatePreferences = useCallback(async (patch: Partial<UserPreferences>, persist = true) => {
    const next = { ...preferences, ...patch };
    apply(next);
    if (persist && session) {
      const payload = Object.fromEntries(Object.entries(patch).filter(([key]) => key !== "updated_at"));
      const remote = await apiPatch<UserPreferences>("/settings/preferences/", payload);
      apply({ ...next, ...remote });
    }
  }, [apply, preferences, session]);

  const value = useMemo(() => ({ preferences, resolvedTheme, loaded, updatePreferences, reloadPreferences }), [preferences, resolvedTheme, loaded, updatePreferences, reloadPreferences]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useThemePreferences() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useThemePreferences must be used inside ThemeProvider");
  return context;
}
