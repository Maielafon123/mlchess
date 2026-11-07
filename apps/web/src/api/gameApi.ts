import { ApiClient } from "./client";
import type { CreateGameV1, GameSnapshotV1, MoveAcceptedV1, SubmitMoveV1 } from "./contracts";

/** Temporary B-008 boundary. Replace with generated A-008 GameSnapshotV1 types. */
export type GameSnapshot = GameSnapshotV1;

export type MoveCommand = SubmitMoveV1;
export type GameCreateOptions = CreateGameV1;

export class GameApi {
  constructor(protected readonly client: ApiClient = new ApiClient()) {}

  create(mode: "ai" | "coach" = "ai", options: Omit<GameCreateOptions, "mode"> = { time_control: null, human_color: "white", ai_profile: "casual" }) {
    return this.client.post<GameSnapshot>("/api/v1/games", { mode, ...options });
  }

  get(gameId: string) {
    return this.client.get<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}`);
  }

  move(gameId: string, command: MoveCommand) {
    return this.client.post<MoveAcceptedV1>(`/api/v1/games/${encodeURIComponent(gameId)}/moves`, command, { idempotencyKey: command.client_move_id }).then((response) => response.snapshot);
  }

  resign(gameId: string, expectedVersion: number) {
    return this.client.post<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/resign`, { expected_version: expectedVersion });
  }
}
