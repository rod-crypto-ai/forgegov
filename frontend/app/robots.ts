import type { MetadataRoute } from "next";
export default function robots():MetadataRoute.Robots{return {rules:{userAgent:"*",allow:["/","/request-access","/support","/terms","/privacy"],disallow:["/api/","/sign-in","/register","/account","/settings","/billing","/capture/","/project-rooms/","/assistant","/platform-admin"]},sitemap:"https://forge-gov.com/sitemap.xml"};}
