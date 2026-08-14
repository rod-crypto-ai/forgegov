"use client";

import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

export function PlatformAdminNav() {
  const [allowed,setAllowed]=useState(false);
  useEffect(()=>{
    let cancelled=false;
    Promise.resolve().then(async()=>{
      try {
        const result=await apiGet<{platform_admin:boolean}>("/platform-admin/me/");
        if(!cancelled) setAllowed(Boolean(result.platform_admin));
      } catch {
        if(!cancelled) setAllowed(false);
      }
    });
    return()=>{cancelled=true};
  },[]);
  if(!allowed) return null;
  return <Link href="/platform-admin" className="platform-admin-nav-link" title="Platform Administration"><ShieldCheck size={17}/><span>Platform Administration</span></Link>;
}
