import { expect, test } from "@playwright/test";

test("navigation reaches play and learning routes", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Играйте, разбирайтесь, растите" })).toBeVisible();

  await page.getByRole("link", { name: "Начать партию" }).click();
  await expect(page).toHaveURL(/\/play$/);
  await expect(page.getByRole("heading", { name: "Игровая зона" })).toBeVisible();

  await page.getByRole("link", { name: "Обучение" }).click();
  await expect(page).toHaveURL(/\/learn$/);
  await expect(page.getByRole("heading", { name: "Обучение" })).toBeVisible();
});
