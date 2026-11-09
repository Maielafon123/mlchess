import { devices, expect, test } from "@playwright/test";

test("guests can analyze a finished challenge and a stranger cannot open it @guest", async ({ browser, baseURL }, testInfo) => {
  test.setTimeout(60000);
  const { defaultBrowserType: _browserType, ...phone } = devices["Pixel 7"];
  void _browserType;
  const first = await browser.newContext({ ...phone, baseURL, viewport: { width: 320, height: 640 } });
  const second = await browser.newContext({ ...phone, baseURL });
  const stranger = await browser.newContext({ baseURL });
  try {
    const host = await first.newPage();
    await host.goto("/play/friend");
    await host.getByRole("button", { name: "Создать вызов" }).click();
    const invitation = host.getByLabel("Ссылка для друга");
    await expect(invitation).toBeVisible();
    const opponent = await second.newPage();
    await opponent.goto(await invitation.inputValue());
    await expect(host.getByText("Ваш ход", { exact: true })).toBeVisible();
    await expect(host.getByRole("link", { name: "Разобрать партию" })).toHaveCount(0);
    await host.locator('.board-frame [data-square="e2"]').tap();
    await host.locator('.board-frame [data-square="e4"]').tap();
    await expect(opponent.locator(".move-history ol li")).toHaveCount(1);
    await opponent.getByRole("button", { name: "Сдаться" }).click();
    await opponent.getByRole("button", { name: "Подтвердить сдачу" }).click();
    await host.getByRole("link", { name: "Разобрать партию" }).click();
    await expect(host.getByRole("heading", { name: "Разбор партии" })).toBeVisible();
    await host.getByRole("button", { name: "Разобрать ход" }).click();
    await expect(host.getByRole("region", { name: "Engine analysis" })).toContainText("Stockfish", { timeout: 25000 });
    await expect.poll(() => host.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth)).toBeLessThanOrEqual(1);
    await host.screenshot({ path: testInfo.outputPath("phone-postgame.png"), fullPage: true });
    const other = await stranger.newPage();
    await other.goto(host.url());
    await expect(other.getByRole("alert").filter({ hasText: "Разбор доступен её участникам" })).toBeVisible();
  } finally {
    await Promise.allSettled([first.close(), second.close(), stranger.close()]);
  }
});
