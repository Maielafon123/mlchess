import { describe, expect, it } from "vitest";
import { acceptsAnalysisResult, formatScore, type EngineAnalysis } from "./analysis";

const base: EngineAnalysis = { request_id: "r1", game_id: "g1", revision: 2, sequence: 4, perspective: "white", score: { kind: "cp", value: 134 }, quality: "good", best_move: { uci: "e2e4", san: "e4" }, alternatives: [], pv: [], status: "ready" };

describe("engine analysis contract helpers", () => {
  it("formats cp, mate and missing evaluations with perspective", () => {
    expect(formatScore({ kind: "cp", value: 134 }, "white")).toBe("+1.34 (white)");
    expect(formatScore({ kind: "mate", value: -3 }, "black")).toBe("-M3 (black)");
    expect(formatScore(null, "white")).toBe("Evaluation unavailable");
  });

  it("rejects duplicate, stale and cross-game results", () => {
    expect(acceptsAnalysisResult(base, { ...base, sequence: 5 })).toBe(true);
    expect(acceptsAnalysisResult(base, { ...base, sequence: 4 })).toBe(false);
    expect(acceptsAnalysisResult(base, { ...base, game_id: "g2", sequence: 5 })).toBe(false);
    expect(acceptsAnalysisResult(base, { ...base, revision: 1, sequence: 5 })).toBe(false);
  });
});
