// @vitest-environment node
import { describe, expect, it } from "vitest";
import { ApiClient } from "./client";

describe("HTTP cancellation and problems", () => {
  it("accepts a successful logout with no body even if JSON content type is present", async () => {
    const client = new ApiClient({ fetchImpl: async () => new Response(null, { status: 204, headers: { "content-type": "application/json" } }) });
    await expect(client.post("/logout", {})).resolves.toBeUndefined();
  });
  it("decodes standard problem+json bodies", async () => {
    const client = new ApiClient({ fetchImpl: async () => new Response(JSON.stringify({ code: "FORBIDDEN", detail: "Denied", request_id: "abc" }), { status: 403, headers: { "content-type": "application/problem+json; charset=utf-8" } }) });
    await expect(client.get("/test")).rejects.toMatchObject({ problem: { code: "FORBIDDEN", detail: "Denied", request_id: "abc" } });
  });

  it("keeps the deadline active while a JSON body stalls, with caller cancellation configured", async () => {
    const caller = new AbortController();
    const client = new ApiClient({ timeoutMs: 30, fetchImpl: async (_url, init) => {
      const stream = new ReadableStream({ start(controller) {
        controller.enqueue(new TextEncoder().encode('{"incomplete":'));
        init?.signal?.addEventListener("abort", () => controller.error(new DOMException("Aborted", "AbortError")), { once: true });
      } });
      return new Response(stream, { headers: { "content-type": "application/json" } });
    } });
    await expect(client.get("/test", { signal: caller.signal })).rejects.toMatchObject({ name: "AbortError" });
    expect(caller.signal.aborted).toBe(false);
  });

  it("propagates a pre-aborted caller signal", async () => {
    const caller = new AbortController();
    caller.abort();
    const client = new ApiClient({ fetchImpl: async (_url, init) => {
      init?.signal?.throwIfAborted();
      return new Response("{}");
    } });
    await expect(client.get("/test", { signal: caller.signal })).rejects.toMatchObject({ name: "AbortError" });
  });
});
