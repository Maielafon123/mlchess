/** Temporary B-010 boundary. Replace with generated A-002/A-014 analysis contracts. */
export type EngineScore = { kind: "cp"; value: number } | { kind: "mate"; value: number } | null;
export type PrincipalVariation = { uci: string; san: string; fen: string };
export type EngineAnalysis = {
  request_id: string;
  game_id: string;
  revision: number;
  sequence: number;
  perspective: "white" | "black";
  score: EngineScore;
  quality: "best" | "good" | "inaccuracy" | "mistake" | "blunder" | null;
  best_move: { uci: string; san: string } | null;
  alternatives: Array<{ uci: string; san: string; score: EngineScore }>;
  pv: PrincipalVariation[];
  status: "pending" | "ready" | "unavailable";
};

export function acceptsAnalysisResult(current: EngineAnalysis | null, incoming: EngineAnalysis) {
  if (!current) return true;
  return incoming.game_id === current.game_id && incoming.revision >= current.revision && incoming.sequence > current.sequence;
}

export function formatScore(score: EngineScore, perspective: "white" | "black") {
  if (!score) return "Evaluation unavailable";
  const sign = score.value > 0 ? "+" : score.value < 0 ? "-" : "";
  const value = score.kind === "cp" ? Math.abs(score.value / 100).toFixed(2) : `M${Math.abs(score.value)}`;
  return `${sign}${value} (${perspective})`;
}
