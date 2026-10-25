import type { MetadataRoute } from "next";
export default function sitemap():MetadataRoute.Sitemap{return ["/","/request-access","/support","/terms","/privacy"].map(path=>({url:`https://forge-gov.com${path}`,changeFrequency:path==="/"?"monthly":"yearly",priority:path==="/"?1:.4}));}
