import { describe, expect, it } from "vitest";
import { selectCriticalDecisions, type PostGameReport } from "./postGameReport";

const report: PostGameReport = { game_id: "g1", status: "ready", result: "loss", analyzed_plies: 8, total_plies: 8, decisions: [
  { ply: 3, phase: "opening", quality: "inaccuracy", played_san: "h3", best_san: "Nf3", played_uci: "h2h3", best_uci: "g1f3", fen: "8/8/8/8/8/8/8/8 w - - 0 1", pv: [], exercise_intent: "Develop before a pawn move" },
  { ply: 7, phase: "middlegame", quality: "blunder", played_san: "Qh5??", best_san: "Qe2", played_uci: "d1h5", best_uci: "d1e2", fen: "8/8/8/8/8/8/8/8 w - - 0 1", pv: [], exercise_intent: "Spot the hanging piece" },
  { ply: 9, phase: "endgame", quality: "good", played_san: "Kf2", best_san: "Kf2", played_uci: "e1f2", best_uci: "e1f2", fen: "8/8/8/8/8/8/8/8 w - - 0 1", pv: [], exercise_intent: null },
] };

describe("post-game report selectors", () => {
  it("filters verified decisions by quality and phase and caps at seven", () => {
    expect(selectCriticalDecisions(report, "blunder", "middlegame")).toHaveLength(1);
    expect(selectCriticalDecisions(report, "all", "opening")[0].best_san).toBe("Nf3");
    expect(selectCriticalDecisions({ ...report, decisions: Array.from({ length: 10 }, (_, index) => ({ ...report.decisions[0], ply: index + 1 })) })).toHaveLength(7);
  });
});
