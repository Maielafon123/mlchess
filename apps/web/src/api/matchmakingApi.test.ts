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
  it("sends time control and rating pool and cancels with DELETE", async () => {
    let body: unknown;
    let method = "";
    server.use(
      http.post("http://localhost/api/v1/matchmaking/tickets", async ({ request }) => { body = await request.json(); return HttpResponse.json({}); }),
      http.delete("http://localhost/api/v1/matchmaking/tickets/t1", ({ request }) => { method = request.method; return HttpResponse.json({}); }),
    );
    const api = new MatchmakingApi(new ApiClient({ baseUrl: "http://localhost" }));
    await api.join("rapid-10+0");
    await api.cancel("t1");
    expect(body).toEqual({ time_control: "rapid-10+0", rating_pool: "rapid-10+0" });
    expect(method).toBe("DELETE");
  });
});
// @vitest-environment node
