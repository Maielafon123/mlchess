import { ApiClient } from "./client";

export type Puzzle = { id: string; fen: string; title: string; difficulty: number; tags: string[]; hints: string[]; solution: Array<{ uci: string; san: string; fen: string }> };
export type PuzzleAttempt = { attempt_id: string; result: "correct" | "incorrect" | "illegal"; completed: boolean; next_ply: number };

export class PuzzleApi {
  constructor(private readonly client?: ApiClient, private readonly allowDemo = false) {}
  static demo() { return new PuzzleApi(undefined, true); }
  async get(id: string): Promise<Puzzle> { if (this.client) return this.client.get<Puzzle>(`/api/v1/learning/puzzles/${encodeURIComponent(id)}`); if (!this.allowDemo) throw new Error("Puzzle API is not configured"); return demoPuzzle; }
  async attempt(id: string, uci: string, attemptId: string): Promise<PuzzleAttempt> { if (this.client) return this.client.post<PuzzleAttempt>(`/api/v1/learning/puzzles/${encodeURIComponent(id)}/attempts`, { uci, attempt_id: attemptId }); if (!this.allowDemo) throw new Error("Puzzle API is not configured"); return { attempt_id: attemptId, result: uci === "d1d8" ? "correct" : "incorrect", completed: uci === "d1d8", next_ply: uci === "d1d8" ? 1 : 0 }; }
}

export const demoPuzzle: Puzzle = { id: "back-rank", title: "Back-rank finish", fen: "6k1/5ppp/8/8/8/8/5PPP/3R2K1 w - - 0 1", difficulty: 1, tags: ["mate", "back-rank"], hints: ["Look at the opponent king's escape squares.", "Can the rook use the open d-file?", "Find the forcing rook move to the back rank."], solution: [{ uci: "d1d8", san: "Rd8#", fen: "3R2k1/5ppp/8/8/8/8/5PPP/6K1 b - - 1 1" }] };
