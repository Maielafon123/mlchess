import { ApiClient } from "../api/client";
import { authConfig } from "./config";
import type { AuthUser } from "./authClient";

let pending: Promise<AuthUser> | null = null;

/** Deduplicates bootstrap across StrictMode and game/auth effects in one tab. */
export function ensureGuestSession(): Promise<AuthUser> {
  if (pending) return pending;
  const api = new ApiClient();
  const bootstrap = () => api.post<AuthUser>("/api/v1/auth/guest", {});
  const request = (async () => {
    if (typeof navigator !== "undefined" && navigator.locks) return await navigator.locks.request("mlchess-guest-bootstrap", bootstrap);
    return await bootstrap();
  })().finally(() => { pending = null; });
  pending = request;
  return request;
}

export async function ensurePublicSession() {
  return authConfig.mode === "guest" || authConfig.mode === "oidc" ? ensureGuestSession() : null;
}
