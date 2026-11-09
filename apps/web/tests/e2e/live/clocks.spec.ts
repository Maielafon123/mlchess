import { devices, expect, test } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("idle timed game expires for both guests without a move @guest", async ({ page, context, browser, baseURL }, testInfo) => {
  const origin = new URL(baseURL!).origin;
  const login = await context.request.post("/api/v1/auth/guest", { headers: { Origin: origin }, data: {} });
  expect(login.status()).toBe(200);
  const csrf = (await context.cookies()).find((item) => item.name === "mlchess_csrf")?.value;
  expect(csrf).toBeTruthy();
  const headers = () => ({ Origin: origin, "X-CSRF-Token": csrf!, "Idempotency-Key": randomUUID() });
  const created = await context.request.post("/api/v1/games", { headers: headers(), data: { mode: "friend", time_control: { initial_ms: 1000, increment_ms: 0 } } });
  expect(created.status()).toBe(201);
  const game = await created.json();
  expect(game.clock.running_side).toBeNull();
  const invite = await context.request.post("/api/v1/invitations", { headers: headers(), data: { game_id: game.id } });
  expect(invite.status()).toBe(201);
  const link = await invite.json();
  let timeoutEvent = false;
  page.on("websocket", (socket) => {
    if (new URL(socket.url()).pathname === `/ws/v1/games/${game.id}`) socket.on("framereceived", (message) => {
      const frame = JSON.parse(String(message.payload));
      if (frame.type === "game.status_changed" && frame.payload.termination === "timeout") timeoutEvent = true;
    });
  });
  await page.goto(`/play/friend?game=${game.id}&invite=${link.invite_id}`);
  await expect(page.getByRole("timer", { name: "Часы белых" })).toContainText("00:01");
  await expect(page.getByRole("status").filter({ hasText: "Связь установлена" })).toBeVisible();
  // Keep real REST refreshes pending until the server's timeout frame arrives.
  // The fallback poll cannot make this test pass by hiding missing WS delivery.
  let releaseRefresh = () => {};
  const refreshGate = new Promise<void>((resolve) => { releaseRefresh = resolve; });
  await page.route(`**/api/v1/games/${game.id}`, async (route) => { await refreshGate; await route.continue().catch(() => {}); });
  const { defaultBrowserType: _browserType, ...phone } = devices[testInfo.project.name.includes("iphone") ? "iPhone 13" : "Pixel 7"];
  void _browserType;
  const opponent = await browser.newContext({ ...phone, baseURL });
  try {
    const other = await opponent.newPage();
    await other.goto(link.invite_url);
    const finished = (target: typeof page) => target.getByRole("status").filter({ hasText: /Партия завершена.*время вышло/ });
    await expect.poll(() => timeoutEvent, { timeout: 12000 }).toBe(true);
    releaseRefresh();
    await expect(finished(page)).toBeVisible({ timeout: 15000 });
    await expect(finished(other)).toBeVisible();
    for (const player of [context, opponent]) {
      const result = await player.request.get(`/api/v1/games/${game.id}`);
      expect(result.status()).toBe(200);
      const saved = await result.json();
      expect(saved).toMatchObject({ status: "finished", version: 2, result: "black", termination: "timeout", moves: [], clock: { white_remaining_ms: 0, black_remaining_ms: 1000, running_side: null } });
    }
    await other.reload();
    await expect(finished(other)).toBeVisible();
    await expect(other.getByRole("timer", { name: "Часы белых" })).toContainText("00:00");
    await other.setViewportSize({ width: 320, height: 640 });
    await expect.poll(() => other.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await other.screenshot({ path: testInfo.outputPath("phone-timeout.png"), fullPage: true });
  } finally { releaseRefresh(); await opponent.close(); }
});
