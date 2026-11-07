/** Temporary B-015 boundary until A-014 post-game analysis is available. */
export type DecisionQuality = "best" | "good" | "inaccuracy" | "mistake" | "blunder";
export type ReportDecision = { ply: number; phase: "opening" | "middlegame" | "endgame"; quality: DecisionQuality; played_san: string; best_san: string; played_uci: string; best_uci: string; fen: string; pv: Array<{ uci: string; san: string; fen: string }>; exercise_intent: string | null };
export type PostGameReport = { game_id: string; status: "pending" | "partial" | "ready"; result: "win" | "loss" | "draw" | "unknown"; decisions: ReportDecision[]; analyzed_plies: number; total_plies: number };

export function selectCriticalDecisions(report: PostGameReport, quality: DecisionQuality | "all" = "all", phase: ReportDecision["phase"] | "all" = "all") {
  return report.decisions.filter((decision) => (quality === "all" || decision.quality === quality) && (phase === "all" || decision.phase === phase)).slice(0, 7);
}
