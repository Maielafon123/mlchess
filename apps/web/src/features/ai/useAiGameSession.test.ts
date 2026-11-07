import { describe, expect, it } from "vitest";
import { acceptsEngineResult } from "./useAiGameSession";

describe("AI result ordering", () => {
  it("accepts the current request at the same or newer server version", () => {
    expect(acceptsEngineResult(4, 4, 8, 8)).toBe(true);
    expect(acceptsEngineResult(4, 4, 8, 9)).toBe(true);
  });

  it("rejects stale request or version responses", () => {
    expect(acceptsEngineResult(5, 4, 8, 9)).toBe(false);
    expect(acceptsEngineResult(5, 5, 10, 9)).toBe(false);
  });
});
