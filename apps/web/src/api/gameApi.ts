import { ApiClient } from "./client";
import type { CreateGameV1, GameSnapshotV1, MoveAcceptedV1, SubmitMoveV1 } from "./contracts";
import type { components } from "../../../../contracts/generated/api";

export type GameSnapshot = GameSnapshotV1;

export type MoveCommand = SubmitMoveV1;
export type GameCreateOptions = CreateGameV1;
export type GameActions = components["schemas"]["GameActionsV1"];
export type HumanAction = "resign" | "draw-offers" | "draw-offers/accept" | "claim-draw";

export function canAdoptSnapshot(current: GameSnapshot | null, next: GameSnapshot) {
  if (!current) return true;
  if (next.id !== current.id) return false;
  if (next.version !== current.version) return next.version > current.version;
  // A delayed read with the same game version must not rewind the displayed clock.
  return !current.clock || !next.clock || Date.parse(next.clock.server_now) >= Date.parse(current.clock.server_now);
}

export class GameApi {
  constructor(protected readonly client: ApiClient = new ApiClient()) {}

  create(mode: "ai" | "coach" = "ai", options: Omit<GameCreateOptions, "mode"> = { time_control: null, human_color: "white", ai_profile: "casual" }, idempotencyKey?: string) {
    return this.client.post<GameSnapshot>("/api/v1/games", { mode, ...options }, { idempotencyKey });
  }

  get(gameId: string, signal?: AbortSignal) {
    return this.client.get<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}`, { signal });
  }

  move(gameId: string, command: MoveCommand) {
    return this.client.post<MoveAcceptedV1>(`/api/v1/games/${encodeURIComponent(gameId)}/moves`, command, { idempotencyKey: command.client_move_id }).then((response) => response.snapshot);
  }

  resign(gameId: string, expectedVersion: number) {
    return this.action(gameId, "resign", expectedVersion);
  }

  actions(gameId: string, signal?: AbortSignal) {
    return this.client.get<GameActions>(`/api/v1/games/${encodeURIComponent(gameId)}/actions`, { signal });
  }

  action(gameId: string, action: HumanAction, expectedVersion: number, idempotencyKey?: string) {
    return this.client.post<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/${action}`, { expected_version: expectedVersion }, { idempotencyKey });
  }
}
