export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
export const API_BASE = API_BASE_URL;

export type ApiList<T = Record<string, unknown>> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
};

type ErrorPayload = { detail?: unknown } & Record<string, unknown>;
let csrfToken: string | null = null;
let csrfRequest: Promise<string> | null = null;

function isUnsafe(method?: string) {
  return !["GET", "HEAD", "OPTIONS", "TRACE"].includes((method ?? "GET").toUpperCase());
}

async function parseResponse(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) return response.json().catch(() => ({}));
  return response.text().catch(() => "");
}

function errorMessage(body: unknown, status: number) {
  if (body && typeof body === "object" && "detail" in body) return String((body as ErrorPayload).detail ?? "");
  if (typeof body === "string" && body.trim()) return body.trim();
  return `Request failed with HTTP ${status}`;
}

async function getCsrfToken(force = false): Promise<string> {
  if (force) {
    csrfToken = null;
    csrfRequest = null;
  }
  if (csrfToken) return csrfToken;
  if (!csrfRequest) {
    csrfRequest = fetch(`${API_BASE_URL}/auth/csrf/`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    }).then(async (response) => {
      const body = await parseResponse(response);
      if (!response.ok || !body || typeof body !== "object" || !("csrfToken" in body)) {
        throw new Error(errorMessage(body, response.status));
      }
      csrfToken = String((body as { csrfToken: unknown }).csrfToken);
      return csrfToken;
    }).finally(() => {
      csrfRequest = null;
    });
  }
  return csrfRequest;
}

async function requestJson<T>(path: string, options: RequestInit = {}, allowRefresh = true, allowCsrfRetry = true): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers ?? {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (isUnsafe(method)) headers.set("X-CSRFToken", await getCsrfToken());

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    method,
    headers,
    cache: options.cache ?? "no-store",
    credentials: "include",
  });
  const body = await parseResponse(response);

  const refreshBlocked = ["/auth/csrf/", "/auth/login/", "/auth/register/", "/auth/refresh/", "/auth/logout/"].includes(path);
  if (response.status === 401 && allowRefresh && !refreshBlocked) {
    await requestJson<{ refreshed: boolean }>("/auth/refresh/", { method: "POST" }, false, true);
    return requestJson<T>(path, options, false, true);
  }

  const message = errorMessage(body, response.status);
  if (response.status === 403 && allowCsrfRetry && message.toLowerCase().includes("csrf")) {
    await getCsrfToken(true);
    return requestJson<T>(path, options, allowRefresh, false);
  }

  if (!response.ok) throw new Error(message);
  return body as T;
}

export async function apiGet<T>(path: string): Promise<T> {
  return requestJson<T>(path);
}

export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, { method: "POST", body: JSON.stringify(payload) });
}

export async function apiPatch<T>(path: string, payload: unknown): Promise<T> {
  return requestJson<T>(path, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function apiDelete(path: string): Promise<void> {
  await requestJson<unknown>(path, { method: "DELETE" });
}

export async function authFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const allowRefresh = path === "/auth/me/" || !path.startsWith("/auth/");
  return requestJson<T>(path, options, allowRefresh);
}

export function normalizeList<T>(payload: T[] | ApiList<T>): T[] {
  if (Array.isArray(payload)) return payload;
  return payload.results ?? [];
}

export async function checkBackend(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health/`, { cache: "no-store", credentials: "include" });
    return response.ok;
  } catch {
    return false;
  }
}
