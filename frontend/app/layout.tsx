import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { AppShell } from "@/components/app-shell";
import { AuthProvider } from "@/components/auth-provider";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "ForgeGov",
  description: "Government contracting intelligence and capture management",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{__html:`(()=>{try{const p=JSON.parse(localStorage.getItem('forgegov-ui-preferences')||'{}');const pref=p.theme||'system';const dark=pref==='dark'||(pref==='system'&&matchMedia('(prefers-color-scheme: dark)').matches);document.documentElement.dataset.theme=dark?'dark':'light';document.documentElement.dataset.themePreference=pref;document.documentElement.dataset.density=p.density||'comfortable';document.documentElement.dataset.reduceMotion=p.reduce_motion?'true':'false';document.documentElement.style.colorScheme=dark?'dark':'light'}catch(e){}})();`}} />
      </head>
      <body>
        <AuthProvider><ThemeProvider><Suspense fallback={<>{children}</>}><AppShell>{children}</AppShell></Suspense></ThemeProvider></AuthProvider>
      </body>
    </html>
  );
}
