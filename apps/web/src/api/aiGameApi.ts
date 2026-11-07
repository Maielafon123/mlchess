import { ApiClient, createIdempotencyKey } from "./client";
import { GameApi, type GameSnapshot } from "./gameApi";
import type { TakebackV1 } from "./contracts";

/** UI-facing aliases; wire payloads are mapped to the generated A contract. */
export type AiProfile = { id: string; label: string };
export const aiProfiles: AiProfile[] = [
  { id: "beginner", label: "Beginner" },
  { id: "casual", label: "Casual" },
  { id: "club", label: "Club" },
  { id: "strong", label: "Strong" },
];
export type AiSide = "white" | "black" | "random";
export type AiGameOptions = { profile_id: string; side: AiSide };
export type AiGameSnapshot = GameSnapshot & {
  mode: "ai";
  ai_profile: AiProfile;
  player_side: Exclude<AiSide, "random">;
  engine_pending: boolean;
  capabilities: GameSnapshot["capabilities"] & { can_takeback: boolean };
};

export function aiView(snapshot: GameSnapshot, profileId: string): AiGameSnapshot {
  const human = snapshot.players.find((player) => player.kind === "human");
  const engine = snapshot.players.find((player) => player.kind === "engine");
  return { ...snapshot, mode: "ai", player_side: human?.side ?? "white",
    ai_profile: aiProfiles.find((profile) => profile.id === profileId) ?? aiProfiles[0],
    engine_pending: snapshot.status === "active" && engine?.side === snapshot.side_to_move };
}

export class AiGameApi extends GameApi {
  constructor(client?: ApiClient) { super(client); }

  createAi(options: AiGameOptions, idempotencyKey?: string) {
    return this.clientPost<GameSnapshot>("/api/v1/games", {
      mode: "ai",
      time_control: null,
      human_color: options.side === "random" ? (globalThis.crypto?.getRandomValues(new Uint8Array(1))[0] ?? 0) % 2 === 0 ? "white" : "black" : options.side,
      ai_profile: options.profile_id,
    }, idempotencyKey);
  }

  takeback(gameId: string, expectedVersion: number, plies: TakebackV1["plies"] = 2, clientActionId = createIdempotencyKey()) {
    return this.clientPost<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/takeback`, { expected_version: expectedVersion, plies, client_action_id: clientActionId });
  }

  private clientPost<T>(path: string, body: unknown, idempotencyKey?: string) {
    return this.client.post<T>(path, body, { idempotencyKey });
  }
}
