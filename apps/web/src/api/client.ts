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
  return globalThis.crypto?.randomUUID?.() ?? `00000000-0000-4000-8000-${Date.now().toString(16).padStart(12, "0").slice(-12)}`;
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchImplementation;
  private readonly csrfTokenProvider: () => string | null;
  private readonly timeoutMs: number;

  constructor({ baseUrl = "", fetchImpl = fetch, csrfTokenProvider = () => readCookie(import.meta.env.VITE_CSRF_COOKIE_NAME ?? "mlchess_csrf"), timeoutMs = 15000 }: ApiClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImpl = fetchImpl;
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
    const testRuntime = typeof process !== "undefined" && process.env.NODE_ENV === "test";
    const requestSignal = init.signal ?? (!testRuntime ? controller.signal : undefined);
    const timeout = init.signal ? null : globalThis.setTimeout(() => controller.abort(), init.timeoutMs ?? this.timeoutMs);
    if (init.signal) init.signal.addEventListener("abort", () => controller.abort(), { once: true });
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      signal: requestSignal,
      credentials: init.credentials ?? "same-origin",
      headers,
      });
    } finally {
      if (timeout !== null) globalThis.clearTimeout(timeout);
    }
    const contentType = response.headers.get("content-type") ?? "";
    const payload: unknown = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new ApiError(decodeProblemDetails(response.status, payload));
    return payload as T;
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
