import type { NextConfig } from "next";

// Staging can keep authenticated API traffic on the frontend origin without
// relaxing SameSite cookies for unrelated onrender.com subdomains.
const apiProxyTarget = process.env.API_PROXY_TARGET?.replace(/\/$/, "");
if (apiProxyTarget) {
  const target = new URL(apiProxyTarget);
  if (target.protocol !== "https:" || target.username || target.password || target.pathname !== "/" || target.search || target.hash) {
    throw new Error("API_PROXY_TARGET must be an HTTPS origin without credentials, path, query, or fragment.");
  }
}

const nextConfig: NextConfig = {
  output: "standalone",
  // Django API routes require their trailing slash. Stripping it here causes
  // an endless redirect between Next.js and Django's APPEND_SLASH handling.
  skipTrailingSlashRedirect: Boolean(apiProxyTarget),
  async rewrites() {
    return apiProxyTarget
      ? [{ source: "/api/:path*", destination: `${apiProxyTarget}/api/:path*/` }]
      : [];
  },
  async headers() {
    return [{
      source: "/(.*)",
      headers: [
        { key: "Strict-Transport-Security", value: "max-age=31536000; includeSubDomains; preload" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "X-Frame-Options", value: "DENY" },
        { key: "Referrer-Policy", value: "same-origin" },
        { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
      ],
    }];
  },
};

export default nextConfig;
