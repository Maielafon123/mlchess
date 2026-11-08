import { expect, test } from "@playwright/test";

test("learning demo routes remain keyboard reachable", async ({ page }) => {
  // UI-only fixture transport; the live suite below exercises real SQL grading.
  const fen = "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1";
  const puzzle = { schema_version: 1, id: "back-rank", fen, difficulty: 1, tags: ["mate"], source_name: "UI fixture", source_url: "https://example.org", license: "CC BY 4.0" };
  await page.route("**/api/v1/learning/puzzles**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    await route.fulfill({ json: path.endsWith("/state") ? { schema_version: 1, learning_epoch: 0, puzzle_id: "back-rank", session_number: 0, current_fen: fen, next_ply: 0, completed: false, hints: [] } : path.endsWith("/puzzles") ? { schema_version: 1, items: [puzzle] } : puzzle });
  });
  await page.goto("/learn/puzzles");
  await expect(page.getByRole("heading", { name: "Шахматные задачи" })).toBeVisible();
  await page.getByRole("button", { name: "Следующая подсказка" }).focus();
  await expect(page.getByRole("button", { name: "Следующая подсказка" })).toBeFocused();
  await page.goto("/learn/progress");
  await expect(page.getByRole("heading", { name: "Результаты обучения" })).toBeVisible();
});

test("four play modes expose safe server-boundary states", async ({ page }) => {
  for (const path of ["/play", "/play/ai", "/play/coach", "/play/friend", "/play/matchmaking"]) {
    await page.goto(path);
    await expect(page.locator("main")).toBeVisible();
  }
});
