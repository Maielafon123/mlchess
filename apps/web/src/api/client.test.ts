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
});
