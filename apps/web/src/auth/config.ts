export type AuthMode = "fake" | "oidc";

export type AuthConfig = {
  mode: AuthMode;
  mePath: string;
  loginPath: string;
  logoutPath: string;
};

export const authConfig: AuthConfig = {
  mode: import.meta.env.VITE_AUTH_MODE === "oidc" ? "oidc" : "fake",
  mePath: import.meta.env.VITE_AUTH_ME_PATH ?? "/api/v1/auth/me",
  loginPath: import.meta.env.VITE_AUTH_LOGIN_PATH ?? "/api/v1/auth/oidc/start",
  logoutPath: import.meta.env.VITE_AUTH_LOGOUT_PATH ?? "/api/v1/auth/logout",
};
