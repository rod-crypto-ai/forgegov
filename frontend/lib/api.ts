export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api";
export const API_BASE = API_BASE_URL;

export type ApiList<T = Record<string, unknown>> = {
  count?: number;
  next?: string | null;
  previous?: string | null;
  results?: T[];
};

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  const contentType = response.headers.get("content-type") ?? "";
  const body = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? String(body.detail) : String(body);
    throw new Error(detail || `Request failed with HTTP ${response.status}`);
  }
  return body as T;
}

export async function apiPost<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof body === "object" && body && "detail" in body ? String(body.detail) : JSON.stringify(body);
    throw new Error(detail || `Request failed with HTTP ${response.status}`);
  }
  return body as T;
}

export function normalizeList<T>(payload: T[] | ApiList<T>): T[] {
  if (Array.isArray(payload)) return payload;
  return payload.results ?? [];
}

export async function checkBackend(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health/`, { cache: "no-store" });
    return response.ok;
  } catch {
    return false;
  }
}

export async function apiPatch<T>(path: string, payload: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body?.detail ?? `Request failed with HTTP ${response.status}`);
  return body as T;
}

export async function apiDelete(path: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}${path}`, { method: "DELETE" });
  if (!response.ok && response.status !== 204) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Request failed with HTTP ${response.status}`);
  }
}
