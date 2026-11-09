import { expect, test } from "@playwright/test";

test("guest coach uses persisted real analysis and survives refresh @guest", async ({ page }, testInfo) => {
  test.setTimeout(90000);
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/play/coach");
  await expect(page.getByLabel("UCI move")).toBeEnabled();
  const gameId = new URL(page.url()).searchParams.get("game");
  await page.locator('.board-frame [data-square="e2"]').click();
  await page.locator('.board-frame [data-square="e4"]').click();
  await expect(page.locator(".coach-explanation")).toContainText("e2e4", { timeout: 40000 });
  await expect(page.locator(".coach-explanation")).not.toContainText("Недостаточно");
  await expect(page.locator('[data-hint-level="solution"]')).toBeEnabled();
  await page.locator('[data-hint-level="solution"]').click();
  await expect(page.locator(".coach-explanation")).toContainText("движок предпочитал", { timeout: 30000 });
  await page.reload();
  await expect(page.locator(".coach-explanation")).toContainText("e2e4", { timeout: 30000 });
  expect(new URL(page.url()).searchParams.get("game")).toBe(gameId);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath("phone-coach.png"), fullPage: true });
  await page.getByRole("button", { name: "Сдаться", exact: true }).click();
  await page.getByRole("button", { name: "Подтвердить сдачу" }).click();
  await expect(page.getByText("Партия завершена: победили чёрные · игрок сдался")).toBeVisible();
  expect(errors).toEqual([]);
});
