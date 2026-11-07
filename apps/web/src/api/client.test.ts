// @vitest-environment node
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { setupServer } from "msw/node";
import { ApiClient } from "./client";
import { handlers } from "./mock/server";

const server = setupServer(...handlers);

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("ApiClient", () => {
  it("returns a typed payload from the deterministic mock", async () => {
    const client = new ApiClient({ baseUrl: "http://localhost" });
    const snapshot = await client.get<{ id: string; status: string }>("/api/v1/mock/snapshot");
    expect(snapshot).toMatchObject({ id: "mock-game-0001", status: "active" });
  });

  it("normalizes ProblemDetails for non-2xx responses", async () => {
    const client = new ApiClient({ baseUrl: "http://localhost" });
    await expect(client.get("/api/v1/mock/problem")).rejects.toMatchObject({
      name: "ApiError",
      problem: { status: 422, code: "MOCK_VALIDATION_ERROR", request_id: "mock-request-0001" },
    });
  });

  it("adds an idempotency key to mutating requests", async () => {
    let key = "";
    const client = new ApiClient({ fetchImpl: (async (_input, init) => { key = new Headers(init?.headers).get("Idempotency-Key") ?? ""; return new Response("{}", { status: 200, headers: { "content-type": "application/json" } }); }) as typeof fetch });
    await client.post("/api/v1/test", {});
    expect(key).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("sends CSRF only for mutations and preserves a caller key", async () => {
    const seen: Array<{ csrf: string | null; key: string | null }> = [];
    const client = new ApiClient({
      csrfTokenProvider: () => "csrf-test-token",
      fetchImpl: (async (_input, init) => {
        const headers = new Headers(init?.headers);
        seen.push({ csrf: headers.get("X-CSRF-Token"), key: headers.get("Idempotency-Key") });
        return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
      }) as typeof fetch,
    });
    await client.get("/api/v1/test");
    await client.post("/api/v1/test", {}, { idempotencyKey: "caller-key" });
    expect(seen).toEqual([{ csrf: null, key: null }, { csrf: "csrf-test-token", key: "caller-key" }]);
  });
});
