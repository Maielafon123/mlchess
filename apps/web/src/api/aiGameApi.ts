import { ApiClient } from "./client";
import { GameApi, type GameSnapshot } from "./gameApi";
import type { TakebackV1 } from "./contracts";

/** UI-facing aliases; wire payloads are mapped to the generated A contract. */
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
    return this.clientPost<AiGameSnapshot>("/api/v1/games", {
      mode: "ai",
      time_control: null,
      human_color: options.side === "random" ? (globalThis.crypto?.getRandomValues(new Uint8Array(1))[0] ?? 0) % 2 === 0 ? "white" : "black" : options.side,
      ai_profile: options.profile_id,
    });
  }

  takeback(gameId: string, expectedVersion: number, plies: TakebackV1["plies"] = 2, clientActionId = globalThis.crypto?.randomUUID?.() ?? `takeback-${Date.now()}`) {
    return this.clientPost<AiGameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/takeback`, { expected_version: expectedVersion, plies, client_action_id: clientActionId });
  }

  private clientPost<T>(path: string, body: unknown) {
    return this.client.post<T>(path, body);
  }
}
