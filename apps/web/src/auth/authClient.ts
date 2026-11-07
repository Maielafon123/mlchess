import { ApiClient, ApiError } from "../api";
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

  async logout() {
    if (this.config.mode === "fake") return;
    await this.api.post(this.config.logoutPath, {});
  }
}
