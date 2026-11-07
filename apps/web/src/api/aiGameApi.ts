import { ApiClient } from "./client";
import { GameApi, type GameSnapshot } from "./gameApi";

/** Temporary B-009 boundary. Replace with generated A-009/A-012 contracts. */
export type AiProfile = { id: string; label: string; rating: number };
export type AiSide = "white" | "black" | "random";
export type AiGameOptions = { profile_id: string; side: AiSide };
export type AiGameSnapshot = GameSnapshot & {
  mode: "ai";
  ai_profile: AiProfile;
  player_side: Exclude<AiSide, "random">;
  engine_pending: boolean;
  capabilities: GameSnapshot["capabilities"] & { can_takeback: boolean };
};

export class AiGameApi extends GameApi {
  constructor(client?: ApiClient) { super(client); }

  createAi(options: AiGameOptions) {
    const humanColor = options.side === "random" ? (globalThis.crypto?.getRandomValues ? (globalThis.crypto.getRandomValues(new Uint8Array(1))[0] % 2 === 0 ? "white" : "black") : "white") : options.side;
    return this.clientPost<AiGameSnapshot>("/api/v1/games", { mode: "ai", time_control: null, human_color: humanColor, ai_profile: options.profile_id });
  }

  takeback(gameId: string, expectedVersion: number) {
    return this.clientPost<AiGameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/takeback`, { expected_version: expectedVersion });
  }

  private clientPost<T>(path: string, body: unknown) {
    return this.client.post<T>(path, body);
  }
}
