import { ApiError, decodeProblemDetails } from "./errors";

type FetchImplementation = typeof fetch;

export type ApiClientOptions = {
  baseUrl?: string;
  fetchImpl?: FetchImplementation;
  csrfTokenProvider?: () => string | null;
  timeoutMs?: number;
};

export type RequestOptions = RequestInit & { idempotencyKey?: string; timeoutMs?: number };

function readCookie(name: string) {
  if (typeof document === "undefined") return null;
  const prefix = `${encodeURIComponent(name)}=`;
  const value = document.cookie.split(";").map((item) => item.trim()).find((item) => item.startsWith(prefix));
  return value ? decodeURIComponent(value.slice(prefix.length)) : null;
}

export function createIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64;
  bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchImplementation;
  private readonly csrfTokenProvider: () => string | null;
  private readonly timeoutMs: number;

  constructor({ baseUrl = "", fetchImpl = fetch, csrfTokenProvider = () => readCookie(import.meta.env.VITE_CSRF_COOKIE_NAME ?? "mlchess_csrf"), timeoutMs = 15000 }: ApiClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImpl = fetchImpl.bind(globalThis);
    this.csrfTokenProvider = csrfTokenProvider;
    this.timeoutMs = timeoutMs;
  }

  async request<T>(path: string, init: RequestOptions = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const method = (init.method ?? "GET").toUpperCase();
    if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
      const csrf = this.csrfTokenProvider();
      if (csrf) headers.set("X-CSRF-Token", csrf);
    }
    const controller = new AbortController();
    const navigationTarget = typeof window === "undefined" ? null : window;
    const navigating = () => controller.abort();
    navigationTarget?.addEventListener("pagehide", navigating, { once: true });
    const abort = () => controller.abort(init.signal?.reason);
    if (init.signal?.aborted) abort();
    else init.signal?.addEventListener("abort", abort, { once: true });
    const timeout = globalThis.setTimeout(() => controller.abort(), init.timeoutMs ?? this.timeoutMs);
    try {
      const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      signal: controller.signal,
      credentials: init.credentials ?? "same-origin",
      headers,
      });
      if (response.ok && (response.status === 204 || response.status === 205 || method === "HEAD")) return undefined as T;
      const contentType = response.headers.get("content-type")?.split(";", 1)[0].trim() ?? "";
      const payload: unknown = contentType === "application/json" || contentType.endsWith("+json") ? await response.json() : await response.text();
      if (!response.ok) throw new ApiError(decodeProblemDetails(response.status, payload));
      return payload as T;
    } finally {
      globalThis.clearTimeout(timeout);
      init.signal?.removeEventListener("abort", abort);
      navigationTarget?.removeEventListener("pagehide", navigating);
    }
  }

  get<T>(path: string, init?: RequestInit) {
    return this.request<T>(path, { ...init, method: "GET" });
  }

  post<T>(path: string, body: unknown, init?: RequestOptions) {
    const headers = new Headers(init?.headers);
    const options = init as RequestOptions | undefined;
    if (!headers.has("Idempotency-Key")) headers.set("Idempotency-Key", options?.idempotencyKey ?? createIdempotencyKey());
    return this.request<T>(path, { ...options, method: "POST", headers, body: JSON.stringify(body) });
  }

  delete<T>(path: string, init?: RequestOptions) {
    return this.request<T>(path, { ...init, method: "DELETE" });
  }
}
