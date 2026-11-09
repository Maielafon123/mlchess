import type { AnalysisResult } from "../../api/analysisApi";
import type { GameSnapshot } from "../../api/gameApi";

export type MistakeReference = { gameId: string; ply: number; phase: "opening" | "tactics" | "endgame" };
const storageKey = (userId: string) => `mlchess-practice:${userId}`;

export function mistakeReferences(userId?: string): MistakeReference[] {
  if (!userId) return [];
  try {
    const saved: unknown = JSON.parse(localStorage.getItem(storageKey(userId)) ?? "[]");
    if (!Array.isArray(saved)) return [];
    return saved.filter((item): item is MistakeReference => item && typeof item.gameId === "string"
      && Number.isSafeInteger(item.ply) && item.ply > 0
      && ["opening", "tactics", "endgame"].includes(item.phase)).slice(0, 12);
  } catch { return []; }
}

export function isOwnMistake(game: GameSnapshot, analysis: AnalysisResult, userId: string) {
  const side = analysis.before_fen.split(" ")[1] === "w" ? "white" : "black";
  return game.status === "finished" && game.id === analysis.game_id && game.revision === analysis.revision
    && game.players.some((player) => player.side === side && player.user_id === userId)
    && ["mistake", "blunder", "inaccuracy"].includes(analysis.quality)
    && analysis.played_move_uci !== analysis.best_move_uci;
}

export function rememberMistake(game: GameSnapshot, analysis: AnalysisResult, userId: string) {
  if (!isOwnMistake(game, analysis, userId)) return;
  const material = analysis.before_fen.split(" ")[0].match(/[qrbn]/gi)?.length ?? 0;
  const phase = material <= 4 ? "endgame" : analysis.ply <= 16 ? "opening" : "tactics";
  const previous = mistakeReferences(userId).filter((item) => item.gameId !== game.id || item.ply !== analysis.ply);
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify([{ gameId: game.id, ply: analysis.ply, phase }, ...previous].slice(0, 12)));
  } catch { /* Training history is optional when storage is blocked. */ }
}
