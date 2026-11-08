import { devices, expect, test } from "@playwright/test";

test("guest challenge works by touch on two phones and survives refresh @guest", async ({ browser, baseURL }, testInfo) => {
  test.setTimeout(60000);
  const { defaultBrowserType: _browserType, ...phone } = devices[testInfo.project.name.includes("iphone") ? "iPhone 13" : "Pixel 7"];
  void _browserType;
  const first = await browser.newContext({ ...phone, baseURL });
  const second = await browser.newContext({ ...phone, baseURL });
  const outsider = await browser.newContext({ ...phone, baseURL });
  try {
    const page = await first.newPage();
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto("/play/friend");
    await page.getByRole("button", { name: "Создать вызов", exact: true }).click();
    const share = page.getByLabel("Ссылка для друга", { exact: true });
    await expect(share).toBeVisible();
    const link = await share.inputValue();
    expect(link).toContain("#token=");
    expect(new URL(page.url()).hash).toBe("");
    const other = await second.newPage();
    other.on("pageerror", (error) => errors.push(error.message));
    await other.goto(link);
    await expect(other.getByRole("status").filter({ hasText: "Ход соперника" })).toBeVisible();
    await expect(page.getByRole("status").filter({ hasText: "Ваш ход" })).toBeVisible();
    expect(new URL(other.url()).hash).toBe("");
    const user1 = await (await first.request.get("/api/v1/me")).json();
    const user2 = await (await second.request.get("/api/v1/me")).json();
    expect(user1.kind).toBe("guest");
    expect(user2.kind).toBe("guest");
    expect(user1.id).not.toBe(user2.id);
    await page.locator('.board-frame [data-square="e2"]').tap();
    await page.locator('.board-frame [data-square="e4"]').tap();
    await expect(other.locator(".move-history ol li")).toHaveCount(1);
    await expect(other.getByRole("status").filter({ hasText: "Ваш ход" })).toBeVisible();
    await other.locator('.board-frame [data-square="e7"]').tap();
    await other.locator('.board-frame [data-square="e5"]').tap();
    await expect(page.locator(".move-history ol li")).toHaveCount(2);
    await expect(other.locator(".move-history ol li")).toHaveCount(2);
    // Keep a real successful poll in flight while reloading. WebKit must see an
    // explicit app cancellation rather than reporting a navigation/CORS error.
    const gameId = new URL(other.url()).searchParams.get("game");
    let releasePoll = () => {};
    const heldPoll = new Promise<void>((resolve) => { releasePoll = resolve; });
    let pollInFlight = false;
    await other.route(`**/api/v1/games/${gameId}`, async (route) => {
      const response = await route.fetch();
      pollInFlight = true;
      await heldPoll;
      await route.fulfill({ response }).catch(() => { /* old document cancelled its fetch */ });
    }, { times: 1 });
    try {
      await expect.poll(() => pollInFlight).toBe(true);
      await other.reload();
    } finally { releasePoll(); }
    await expect(other.locator(".move-history ol li")).toHaveCount(2);
    expect((await (await second.request.get("/api/v1/me")).json()).id).toBe(user2.id);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
    await page.screenshot({ path: testInfo.outputPath("phone-game.png"), fullPage: true });
    const intruder = await outsider.newPage();
    await intruder.goto(link);
    await expect(intruder.getByRole("alert")).toBeVisible();
    await expect(intruder.getByRole("region", { name: "Game board" })).toHaveCount(0);
    await other.getByRole("button", { name: "Сдаться", exact: true }).click();
    await expect(page.getByRole("status").filter({ hasText: "Партия завершена" })).toBeVisible();
    await expect(other.getByRole("status").filter({ hasText: "Партия завершена" })).toBeVisible();
    expect(errors).toEqual([]);
  } finally { await Promise.allSettled([first.close(), second.close(), outsider.close()]); }
});

test("small phone pages have no horizontal overflow @guest", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 740 });
  for (const path of ["/", "/play/friend", "/play/ai", "/play/coach", "/learn"]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
    await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
  }
});

test("guest AI keeps the game on refresh and supports the black side @guest", async ({ page }) => {
  test.setTimeout(60000);
  await page.goto("/play/ai");
  await expect(page.getByLabel("UCI move")).toBeEnabled();
  const gameId = new URL(page.url()).searchParams.get("game");
  await page.locator('.board-frame [data-square="e2"]').tap();
  await page.locator('.board-frame [data-square="e4"]').tap();
  await expect(page.locator(".move-history ol li")).toHaveCount(2, { timeout: 20000 });
  await page.reload();
  await expect(page.locator(".move-history ol li")).toHaveCount(2);
  expect(new URL(page.url()).searchParams.get("game")).toBe(gameId);
  await page.getByLabel("Your side").selectOption("black");
  await expect(page.locator(".move-history ol li")).toHaveCount(1, { timeout: 20000 });
  await expect(page.getByLabel("UCI move")).toBeEnabled();
  await page.locator('.board-frame [data-square="e7"]').tap();
  await page.locator('.board-frame [data-square="e5"]').tap();
  await expect(page.locator(".move-history ol li")).toHaveCount(3, { timeout: 20000 });
  await page.getByRole("button", { name: "Take back", exact: true }).click();
  await expect(page.locator(".move-history ol li")).toHaveCount(1);
});
