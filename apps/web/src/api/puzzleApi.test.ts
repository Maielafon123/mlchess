import { describe, expect, it } from "vitest";
import { PuzzleApi } from "./puzzleApi";

describe("PuzzleApi", () => {
  it("grades through the demo server boundary and never trusts a client flag", async () => {
    const api = PuzzleApi.demo();
    const puzzle = await api.get("back-rank");
    const wrong = await api.attempt(puzzle.id, "g1f1", "a1");
    const right = await api.attempt(puzzle.id, "d1d8", "a2");
    expect(wrong.result).toBe("incorrect");
    expect(right.completed).toBe(true);
  });
});
