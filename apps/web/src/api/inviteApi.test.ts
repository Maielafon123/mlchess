import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiClient } from "./client";
import { InviteApi } from "./inviteApi";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("InviteApi", () => {
  it("uses the invitations contract", async () => {
    let path = "";
    server.use(http.post("http://localhost/api/v1/invitations", ({ request }) => { path = new URL(request.url).pathname; return HttpResponse.json({ invite_id: "i" }); }));
    await new InviteApi(new ApiClient({ baseUrl: "http://localhost" })).create();
    expect(path).toBe("/api/v1/invitations");
  });
});
