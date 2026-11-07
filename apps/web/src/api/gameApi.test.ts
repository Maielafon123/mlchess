import { afterAll, afterEach, beforeAll, describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { setupServer } from "msw/node";
import { ApiClient } from "./client";
import { GameApi, type GameSnapshot } from "./gameApi";
import { mockSnapshot } from "./mock/fixtures";
import { handlers } from "./mock/server";

const server = setupServer(...handlers);
const snapshot = {
  ...mockSnapshot,
  fen: "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
  moves: [],
  capabilities: { can_move: true, can_takeback: true, can_analyze_now: true },
} as unknown as GameSnapshot;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe("GameApi move flow", () => {
  const api = () => new GameApi(new ApiClient({ baseUrl: "http://localhost" }));

  it("creates a game and sends the optimistic command envelope", async () => {
    let received: unknown;
    server.use(
      http.post("http://localhost/api/v1/games", () => HttpResponse.json(snapshot)),
      http.post("http://localhost/api/v1/games/game-1/moves", async ({ request }) => {
        received = await request.json();
        return HttpResponse.json({ ...snapshot, version: 2, moves: [{ ply: 1, san: "e4", uci: "e2e4" }] });
      }),
    );
    const game = api();
    expect((await game.create()).id).toBe(snapshot.id);
    await game.move("game-1", { uci: "e2e4", client_move_id: "client-1", expected_version: 1 });
    expect(received).toEqual({ uci: "e2e4", client_move_id: "client-1", expected_version: 1 });
  });

  it.each([
    ["illegal", 422, "ILLEGAL_MOVE"],
    ["duplicate", 409, "DUPLICATE_COMMAND"],
  ])("normalizes %s move rejection", async (_label, status, code) => {
    server.use(http.post("*/api/v1/games/game-1/moves", () => HttpResponse.json({ status, code, title: "Rejected", detail: "Move rejected", request_id: "req-1" }, { status })));
    await expect(api().move("game-1", { uci: "e2e5", client_move_id: "client-1", expected_version: 1 })).rejects.toMatchObject({ problem: { status, code } });
  });

  it("preserves a stale-version rollback snapshot", async () => {
    server.use(http.post("*/api/v1/games/game-1/moves", () => HttpResponse.json({ status: 409, code: "STALE_VERSION", title: "Conflict", detail: "Refresh required", request_id: "req-2", snapshot }, { status: 409 })));
    await expect(api().move("game-1", { uci: "e2e4", client_move_id: "client-2", expected_version: 1 })).rejects.toMatchObject({ problem: { code: "STALE_VERSION", snapshot } });
  });
});
