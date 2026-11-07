import { expect, test } from "@playwright/test";

test("two real users, durable engine reply, takeback and private game ACL", async ({ browser, baseURL }) => {
  test.setTimeout(60000);
  const first = await browser.newContext({ baseURL });
  const second = await browser.newContext({ baseURL });
  try {
    const origin = new URL(baseURL!).origin;
    for (const [context, name] of [[first, "Live first " + Date.now()], [second, "Live second " + Date.now()]] as const) {
      const login = await context.request.post("/api/v1/auth/dev-login", { data: { display_name: name }, headers: { Origin: origin } });
      expect(login.status()).toBe(200);
    }
    const page = await first.newPage();
    await page.goto("/");
    await expect(page.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
    const other = await second.newPage();
    await other.goto("/");
    await expect(other.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
    const user1 = await (await first.request.get("/api/v1/me")).json();
    const user2 = await (await second.request.get("/api/v1/me")).json();
    expect(user1.id).not.toBe(user2.id);
    const created = page.waitForResponse((response) => response.url().endsWith("/api/v1/games") && response.request().method() === "POST");
    await page.goto("/play/ai");
    const response = await created;
    expect(response.status()).toBe(201);
    const game = await response.json();
    expect((await second.request.get(`/api/v1/games/${game.id}`)).status()).toBe(403);
    const input = page.getByLabel("UCI move");
    await page.getByText("Ввести ход с клавиатуры", { exact: true }).click();
    await expect(input).toBeEnabled();
    await input.fill("e2e4");
    await page.getByRole("button", { name: "Submit", exact: true }).click();
    await expect(page.locator(".move-history ol li")).toHaveCount(2, { timeout: 20000 });
    await expect(input).toBeEnabled();
    const stored = await (await first.request.get(`/api/v1/games/${game.id}`)).json();
    expect(stored.ply).toBe(2);
    expect(stored.moves[0].uci).toBe("e2e4");
    await page.reload();
    await expect(page.locator(".move-history ol li")).toHaveCount(2);
    expect(new URL(page.url()).searchParams.get("game")).toBe(game.id);
    await page.getByRole("button", { name: "Take back", exact: true }).click();
    await expect(page.getByText("No moves yet.", { exact: true })).toBeVisible();
    const undone = await (await first.request.get(`/api/v1/games/${game.id}`)).json();
    expect(undone.ply).toBe(0);
    expect(undone.revision).toBeGreaterThan(stored.revision);
    await page.reload();
    await expect(page.getByRole("button", { name: "Выйти", exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Выйти", exact: true }).click();
    await expect(page.getByRole("button", { name: "Войти", exact: true })).toBeVisible();
    expect((await first.request.get(`/api/v1/games/${game.id}`)).status()).toBe(401);
    expect((await second.request.get("/api/v1/me")).status()).toBe(200);
  } finally {
    await Promise.allSettled([first.close(), second.close()]);
  }
});
