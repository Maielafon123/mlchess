import { ApiClient, ApiError } from "../api";
import { createIdempotencyKey } from "../api/client";
import type { AuthConfig } from "./config";
import type { components } from "../../../../contracts/generated/api";

export type AuthUser = {
  id: string;
  kind?: "account" | "guest";
  display_name: string;
};

export class AuthClient {
  constructor(private readonly api: ApiClient, private readonly config: AuthConfig) {}

  async getMe(): Promise<AuthUser | null> {
    try {
      return await this.api.get<AuthUser>(this.config.mePath);
    } catch (error) {
      if (error instanceof ApiError && error.problem.status === 401) return null;
      throw error;
    }
  }

  async providers(signal?: AbortSignal) {
    const response = await this.api.get<components["schemas"]["AuthProvidersV1"]>("/api/v1/auth/providers", { signal });
    return response.schema_version === 1 && response.google === true;
  }

  async beginSignIn() {
    if (this.config.mode !== "guest" && this.config.mode !== "oidc") return;
    const response = await this.api.post<components["schemas"]["GoogleLoginStartV1"]>(this.config.loginPath, {});
    const destination = new URL(response.authorization_url);
    if (response.schema_version !== 1 || destination.origin !== "https://accounts.google.com" ||
      destination.pathname !== "/o/oauth2/v2/auth" || destination.username || destination.password || destination.hash) {
      throw new Error("Unexpected login destination");
    }
    window.location.assign(destination.href);
  }

  developmentSignIn() {
    if (this.config.mode !== "development" || !import.meta.env.DEV) throw new Error("Development login disabled");
    return this.api.post<AuthUser>("/api/v1/auth/dev-login", { display_name: `Dev ${createIdempotencyKey().slice(0, 8)}` });
  }

  async logout() {
    if (this.config.mode === "fake") return;
    await this.api.post(this.config.logoutPath, {});
  }
}
