import { describe, expect, it } from "vitest";
import { learningTransport, initialState } from "../test/learningFixtures";

describe("PuzzleApi", () => {
  it("sends only a move and expected server cursor with a stable command UUID", async () => {
    const { puzzles, fetchImpl } = learningTransport();
    const key = "00000000-0000-4000-8000-000000000001";
    await puzzles.attempt("back-rank", "d1d8", initialState, key);
    const init = fetchImpl.mock.calls[0][1]!;
    expect(JSON.parse(String(init.body))).toEqual({ schema_version: 1, learning_epoch: 0, uci: "d1d8", attempt_id: key, session_number: 0, expected_ply: 0 });
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe(key);
    expect(new Headers(init.headers).get("X-CSRF-Token")).toBe("test-csrf");
  });
});
