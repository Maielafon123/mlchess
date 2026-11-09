// @vitest-environment node
import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiClient } from "./client";
import { MatchmakingApi } from "./matchmakingApi";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("MatchmakingApi", () => {
  it("sends the versioned pool and preserves command keys and CSRF", async () => {
    let body: unknown;
    const commands: (string | null)[][] = [];
    const headers = (request: Request) => [request.method, request.headers.get("Idempotency-Key"), request.headers.get("X-CSRF-Token")];
    server.use(
      http.post("http://localhost/api/v1/matchmaking/tickets", async ({ request }) => { body = await request.json(); commands.push(headers(request)); return HttpResponse.json({}); }),
      http.delete("http://localhost/api/v1/matchmaking/tickets/t1", ({ request }) => { commands.push(headers(request)); return HttpResponse.json({}); }),
    );
    const api = new MatchmakingApi(new ApiClient({ baseUrl: "http://localhost", csrfTokenProvider: () => "csrf" }));
    await api.join("rapid-10+0", "join-key");
    await api.cancel("t1", "cancel-key");
    expect(body).toEqual({ schema_version: 1, pool: "rapid-10+0" });
    expect(commands).toEqual([["POST", "join-key", "csrf"], ["DELETE", "cancel-key", "csrf"]]);
  });
});
