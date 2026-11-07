import { ApiClient } from "./client";

/** Temporary B-008 boundary. Replace with generated A-008 GameSnapshotV1 types. */
export type GameSnapshot = {
  schema_version: number;
  id: string;
  status: "active" | "finished" | "resigned";
  fen: string;
  moves: Array<{ ply: number; san: string; uci: string }>;
  version: number;
  revision: number;
  capabilities: { can_move: boolean; can_resign: boolean };
};

export type MoveCommand = {
  uci: string;
  client_move_id: string;
  expected_version: number;
};

export class GameApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}

  create() {
    return this.client.post<GameSnapshot>("/api/v1/games", { mode: "local" });
  }

  get(gameId: string) {
    return this.client.get<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}`);
  }

  move(gameId: string, command: MoveCommand) {
    return this.client.post<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/moves`, command);
  }

  resign(gameId: string, expectedVersion: number) {
    return this.client.post<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/resign`, { expected_version: expectedVersion });
  }
}
