import { describe, expect, it } from "vitest";
import { resolveAuthMode } from "./config";

describe("production auth configuration", () => {
  it("allows fake auth only outside production", () => {
    expect(resolveAuthMode(undefined, false)).toBe("fake");
    expect(() => resolveAuthMode(undefined, true)).toThrow(/VITE_AUTH_MODE/);
    expect(() => resolveAuthMode("fake", true)).toThrow(/fake auth/);
    expect(resolveAuthMode("oidc", true)).toBe("oidc");
    expect(resolveAuthMode("guest", true)).toBe("guest");
    expect(resolveAuthMode("development", false)).toBe("development");
    expect(() => resolveAuthMode("development", true)).toThrow(/VITE_AUTH_MODE/);
  });
});
