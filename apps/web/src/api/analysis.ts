import { Chess } from "chess.js";
import type { components } from "../../../../contracts/generated/api";
import type { AnalysisResult } from "./analysisApi";

export type EngineAnalysis = AnalysisResult;
export type EngineScore = components["schemas"]["ScoreV1"] | null;

/** The v1 score is always White POV; never relabel a score as Black POV. */
export function formatScore(score: EngineScore) {
  if (!score) return "Evaluation unavailable";
  const sign = score.value > 0 ? "+" : score.value < 0 ? "-" : "";
  const value = score.kind === "cp" ? Math.abs(score.value / 100).toFixed(2) : `M${Math.abs(score.value)}`;
  return `${sign}${value} (white)`;
}

export function replayPv(beforeFen: string, moves: readonly string[]) {
  const board = new Chess(beforeFen);
  return moves.map((uci, index) => {
    const move = board.move({ from: uci.slice(0, 2), to: uci.slice(2, 4), promotion: uci[4] });
    return { ply: index + 1, uci, san: move.san, fen: board.fen() };
  });
}
