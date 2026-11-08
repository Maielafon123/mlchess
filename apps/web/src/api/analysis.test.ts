import { describe, expect, it } from "vitest";
import { Chess } from "chess.js";
import { formatScore, replayPv } from "./analysis";

describe("generated analysis consumer", () => {
  it("keeps White POV and keeps mate distances distinct from centipawns", () => {
    expect(formatScore({ kind: "cp", value: 134, pov: "white" })).toBe("+1.34 (white)");
    expect(formatScore({ kind: "mate", value: -3, pov: "white" })).toBe("-M3 (white)");
    expect(formatScore({ kind: "mate", value: 0, pov: "white" })).toBe("M0 (white)");
    expect(formatScore(null)).toBe("Evaluation unavailable");
  });
  it("reconstructs a legal PV and rejects an illegal continuation", () => {
    const replay = replayPv(new Chess().fen(), ["e2e4", "e7e5"]);
    expect(replay.map((move) => move.san)).toEqual(["e4", "e5"]);
    expect(new Chess(replay[1].fen).turn()).toBe("w");
    expect(() => replayPv(new Chess().fen(), ["e2e4", "a1a8"])).toThrow();
  });
});
