import { expect, test } from "@playwright/test";

test("live backend exposes health and session endpoints", async ({ request }) => {
  const health = await request.get("/health/live");
  expect(health.status()).toBe(200);
  expect((await health.json()).status).toBe("ok");

  const me = await request.get("/api/v1/me");
  expect([200, 401]).toContain(me.status());
  expect(me.headers()["content-type"]).toContain(me.status() === 200 ? "application/json" : "application/problem+json");
});
