import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiClient } from "./client";
import { AiGameApi } from "./aiGameApi";
import { handlers } from "./mock/server";

const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("AiGameApi", () => {
  it("sends profile and side when creating an AI game", async () => {
    let received: unknown;
    server.use(http.post("http://localhost/api/v1/games", async ({ request }) => { received = await request.json(); return HttpResponse.json({ id: "ai-1" }); }));
    await new AiGameApi(new ApiClient({ baseUrl: "http://localhost" })).createAi({ profile_id: "club", side: "black" });
    expect(received).toMatchObject({ mode: "ai", time_control: null, human_color: "black", ai_profile: "club" });
  });

  it("calls takeback with the expected server version", async () => {
    let received: unknown;
    server.use(http.post("*/api/v1/games/ai-1/takeback", async ({ request }) => { received = await request.json(); return HttpResponse.json({ id: "ai-1" }); }));
    await new AiGameApi(new ApiClient({ baseUrl: "http://localhost" })).takeback("ai-1", 7);
    expect(received).toMatchObject({ expected_version: 7, plies: 2 });
    expect((received as { client_action_id: string }).client_action_id).toMatch(/^[0-9a-f-]{36}$|^takeback-/);
  });
});
