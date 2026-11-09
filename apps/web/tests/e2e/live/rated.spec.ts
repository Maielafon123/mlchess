import { devices, expect, test, type Page } from "@playwright/test";
import { randomUUID } from "node:crypto";

const queue = "/api/v1/matchmaking/tickets";
const ready = (page: Page) => page.getByRole("status").filter({ hasText: "Связь установлена" });
const status = (page: Page, label: string) => page.getByRole("status").filter({ hasText: label });

test("rated search pairs two accounts, streams a move and saves both Elo results", async ({ browser, baseURL }, testInfo) => {
  test.setTimeout(60000);
  const { defaultBrowserType: _browserType, ...phone } = devices["Pixel 7"];
  void _browserType;
  const first = await browser.newContext({ ...phone, baseURL, viewport: { width: 320, height: 640 } });
  const second = await browser.newContext({ ...phone, baseURL });
  try {
    const origin = new URL(baseURL!).origin;
    for (const [context, label] of [[first, "White or black"], [second, "Rated opponent"]] as const) {
      const login = await context.request.post("/api/v1/auth/dev-login", {
        headers: { Origin: origin }, data: { display_name: label + " " + randomUUID().slice(0, 8) },
      });
      expect(login.status()).toBe(200);
    }
    const [one, two] = await Promise.all([first.newPage(), second.newPage()]);
    const moves = new Map<Page, number>();
    for (const page of [one, two]) {
      page.on("websocket", (socket) => {
        if (!new URL(socket.url()).pathname.startsWith("/ws/v1/games/")) return;
        socket.on("framereceived", (event) => {
          if (JSON.parse(String(event.payload)).type === "game.move_committed") moves.set(page, (moves.get(page) ?? 0) + 1);
        });
      });
    }
    await Promise.all([one.goto("/play/matchmaking"), two.goto("/play/matchmaking")]);
    const search = (page: Page) => page.getByRole("button", { name: "Найти соперника" });
    await search(one).click();
    await expect(status(one, "Ищем соперника")).toBeVisible();
    await one.getByRole("button", { name: "Отменить поиск" }).click();
    await expect(status(one, "Поиск отменён")).toBeVisible();
    await search(one).click();
    await expect(status(one, "Ищем соперника")).toBeVisible();
    await one.reload();
    await expect(status(one, "Ищем соперника")).toBeVisible();
    await search(two).click();
    await Promise.all([expect(ready(one)).toBeVisible(), expect(ready(two)).toBeVisible()]);
    const firstTicket = new URL(one.url()).searchParams.get("ticket");
    const secondTicket = new URL(two.url()).searchParams.get("ticket");
    expect(firstTicket).toBeTruthy();
    expect(secondTicket).toBeTruthy();
    expect(firstTicket).not.toBe(secondTicket);
    expect((await second.request.get(queue + "/" + firstTicket)).status()).toBe(403);
    const tickets = await Promise.all([
      first.request.get(queue + "/" + firstTicket).then((response) => response.json()),
      second.request.get(queue + "/" + secondTicket).then((response) => response.json()),
    ]);
    expect(tickets[0].game_id).toBeTruthy();
    expect(tickets[0].game_id).toBe(tickets[1].game_id);
    const ratingUrl = "/api/v1/games/" + tickets[0].game_id + "/rating";
    const detail = await (await first.request.get(ratingUrl)).json();
    const [white, black] = detail.side === "white" ? [one, two] : [two, one];
    await expect(status(white, "Ваш ход")).toBeVisible();
    await expect(black.getByRole("timer", { name: "Часы чёрных" })).toContainText("10:00");
    await white.locator('.board-frame [data-square="e2"]').tap();
    await white.locator('.board-frame [data-square="e4"]').tap();
    await expect(black.locator(".move-history ol li")).toHaveCount(1);
    await expect.poll(() => moves.get(black) ?? 0).toBeGreaterThan(0);
    await white.getByRole("button", { name: "Предложить ничью" }).click();
    await expect(black.getByRole("button", { name: "Принять ничью" })).toBeVisible();
    await black.getByRole("button", { name: "Сдаться" }).click();
    await expect(status(white, "Рейтинг 1200 → 1216 (+16)")).toBeVisible();
    await expect(status(black, "Рейтинг 1200 → 1184 (-16)")).toBeVisible();
    await white.reload();
    await expect(status(white, "Рейтинг 1200 → 1216 (+16)")).toBeVisible();
    await expect.poll(() => one.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await one.screenshot({ path: testInfo.outputPath("phone-rated.png"), fullPage: true });
  } finally {
    await Promise.allSettled([first.close(), second.close()]);
  }
});

test("a guest can use a challenge link and cannot enter the rated queue @guest", async ({ page, context, baseURL }) => {
  await page.goto("/play/matchmaking");
  await expect(page.getByRole("link", { name: "Сыграть с другом без регистрации" })).toHaveAttribute("href", "/play/friend");
  await expect(page.getByRole("button", { name: "Найти соперника" })).toHaveCount(0);
  const origin = new URL(baseURL!).origin;
  const login = await context.request.post("/api/v1/auth/guest", { headers: { Origin: origin }, data: {} });
  expect(login.status()).toBe(200);
  const csrf = (await context.cookies()).find((item) => item.name === "mlchess_csrf")?.value;
  expect(csrf).toBeTruthy();
  const denied = await context.request.post(queue, {
    headers: { Origin: origin, "X-CSRF-Token": csrf!, "Idempotency-Key": randomUUID() },
    data: { schema_version: 1, pool: "rapid-10+0" },
  });
  expect(denied.status()).toBe(403);
});
