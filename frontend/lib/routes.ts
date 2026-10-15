const PUBLIC_ROUTE_PREFIXES = [
  "/sign-in",
  "/register",
  "/forgot-password",
  "/reset-password",
  "/verify-email",
  "/terms",
  "/privacy",
] as const;

export function isPublicRoute(pathname: string) {
  return pathname === "/" || PUBLIC_ROUTE_PREFIXES.some((path) => pathname === path || pathname.startsWith(`${path}/`));
}
