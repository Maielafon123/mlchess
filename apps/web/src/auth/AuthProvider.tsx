import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { ApiClient } from "../api";
import { authConfig, type AuthConfig } from "./config";
import { AuthClient, type AuthUser } from "./authClient";
import { ensureGuestSession } from "./guestSession";

export type AuthStatus = "loading" | "guest" | "authenticated" | "forbidden" | "error";

type AuthContextValue = {
  status: AuthStatus;
  user: AuthUser | null;
  errorCode: string | null;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children, config = authConfig }: { children: ReactNode; config?: AuthConfig }) {
  const client = useMemo(() => new AuthClient(new ApiClient(), config), [config]);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    if (config.mode === "fake") {
      setUser(null);
      setStatus("guest");
      return () => { active = false; };
    }
    void (config.mode === "guest" ? ensureGuestSession() : client.getMe()).then((currentUser) => {
      if (!active) return;
      setUser(currentUser);
      setStatus(currentUser ? "authenticated" : "guest");
    }).catch((error: unknown) => {
      if (!active) return;
      const code = error instanceof Error ? error.name : "AUTH_BOOTSTRAP_FAILED";
      setErrorCode(code);
      setStatus("error");
    });
    return () => { active = false; };
  }, [client, config.mode]);

  const value = useMemo<AuthContextValue>(() => ({
    status,
    user,
    errorCode,
    signIn: async () => {
      setErrorCode(null);
      if (config.mode === "fake") {
        setUser({ id: "fake-student", display_name: "Demo student" });
        setStatus("authenticated");
        return;
      }
      if (config.mode === "development") {
        try {
          setUser(await client.developmentSignIn());
          setStatus("authenticated");
        } catch (error: unknown) {
          setErrorCode(error instanceof Error ? error.name : "AUTH_LOGIN_FAILED");
          setStatus("error");
        }
        return;
      }
      if (config.mode === "guest") {
        try {
          setUser(await ensureGuestSession());
          setStatus("authenticated");
        } catch (error: unknown) {
          setErrorCode(error instanceof Error ? error.name : "GUEST_SESSION_FAILED");
          setStatus("error");
        }
        return;
      }
      client.beginSignIn();
    },
    signOut: async () => {
      try {
        await client.logout();
        setUser(null);
        setStatus("guest");
      } catch (error: unknown) {
        const code = error instanceof Error ? error.name : "AUTH_LOGOUT_FAILED";
        setErrorCode(code);
        setStatus("error");
      }
    },
  }), [client, config.mode, errorCode, status, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
