export type AuthMode = "fake" | "oidc";

export type AuthConfig = {
  mode: AuthMode;
  mePath: string;
  loginPath: string;
  logoutPath: string;
};

export function resolveAuthMode(raw: string | undefined, production = import.meta.env.PROD): AuthMode {
  if (raw === "oidc" || raw === "fake") return raw;
  if (!production) return "fake";
  throw new Error("VITE_AUTH_MODE must be explicitly set to 'oidc' for production builds");
}

export const authConfig: AuthConfig = {
  mode: resolveAuthMode(import.meta.env.VITE_AUTH_MODE),
  mePath: import.meta.env.VITE_AUTH_ME_PATH ?? "/api/v1/auth/me",
  loginPath: import.meta.env.VITE_AUTH_LOGIN_PATH ?? "/api/v1/auth/oidc/start",
  logoutPath: import.meta.env.VITE_AUTH_LOGOUT_PATH ?? "/api/v1/auth/logout",
};
