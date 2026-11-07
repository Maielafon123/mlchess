import { describe, expect, it, vi } from "vitest";
import { SafeMoveRetry, backoffDelay, withRetry } from "./realtimeResilience";

describe("realtime resilience", () => {
  it("caps exponential backoff", () => { expect(backoffDelay(0)).toBe(250); expect(backoffDelay(5)).toBe(4000); });
  it("retries transient failures", async () => { let calls = 0; const result = await withRetry(async () => { calls += 1; if (calls < 3) throw new Error("offline"); return "ok"; }, { retries: 2, sleep: async () => undefined }); expect(result).toBe("ok"); expect(calls).toBe(3); });
  it("reuses the same client move id operation", async () => { const retry = new SafeMoveRetry<string>(); const operation = vi.fn(async () => "accepted"); retry.register("move-1", operation); await retry.retry("move-1"); await retry.retry("move-1"); expect(operation).toHaveBeenCalledTimes(2); });
});
