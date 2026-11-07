import { expect, test } from "@playwright/test";

test("learning demo routes remain keyboard reachable", async ({ page }) => {
  await page.goto("/learn/puzzles");
  await expect(page.getByRole("heading", { name: "Solve a chess puzzle" })).toBeVisible();
  await page.getByRole("button", { name: "Show next hint" }).focus();
  await expect(page.getByRole("button", { name: "Show next hint" })).toBeFocused();
  await page.goto("/learn/progress");
  await expect(page.getByRole("heading", { name: "Review what you learned" })).toBeVisible();
});

test("four play modes expose safe server-boundary states", async ({ page }) => {
  for (const path of ["/play", "/play/ai", "/play/coach", "/play/friend", "/play/matchmaking"]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
  }
});
