import { ApiClient, ApiError } from "../api";
import { createIdempotencyKey } from "../api/client";
import type { AuthConfig } from "./config";

export type AuthUser = {
  id: string;
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

  beginSignIn() {
    if (this.config.mode === "fake") return;
    window.location.assign(this.config.loginPath);
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
