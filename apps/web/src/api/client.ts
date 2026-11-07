import { ApiError, decodeProblemDetails } from "./errors";

type FetchImplementation = typeof fetch;

export type ApiClientOptions = {
  baseUrl?: string;
  fetchImpl?: FetchImplementation;
};

export class ApiClient {
  private readonly baseUrl: string;
  private readonly fetchImpl: FetchImplementation;

  constructor({ baseUrl = "", fetchImpl = fetch }: ApiClientOptions = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, "");
    this.fetchImpl = fetchImpl;
  }

  async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (init.body !== undefined && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      ...init,
      credentials: init.credentials ?? "include",
      headers,
    });
    const contentType = response.headers.get("content-type") ?? "";
    const payload: unknown = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new ApiError(decodeProblemDetails(response.status, payload));
    return payload as T;
  }

  get<T>(path: string, init?: RequestInit) {
    return this.request<T>(path, { ...init, method: "GET" });
  }

  post<T>(path: string, body: unknown, init?: RequestInit) {
    return this.request<T>(path, { ...init, method: "POST", body: JSON.stringify(body) });
  }
}
