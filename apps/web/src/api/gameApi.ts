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
  mode?: "ai" | "coach" | "friend" | "rated";
  analysis_id?: string | null;
  capabilities: { can_move: boolean; can_resign: boolean };
};

export type MoveCommand = {
  uci: string;
  client_move_id: string;
  expected_version: number;
};

export type GameCreateOptions = {
  mode: "friend" | "ai" | "coach";
  time_control?: { initial_ms: number; increment_ms: number } | null;
  human_color?: "white" | "black";
  ai_profile?: string;
};

export type MoveAccepted = { schema_version: 1; client_move_id: string; move: { ply: number; san: string; uci: string }; snapshot: GameSnapshot };

export class GameApi {
  constructor(protected readonly client: ApiClient = new ApiClient()) {}

  create(mode: "ai" | "coach" = "ai", options: Omit<GameCreateOptions, "mode"> = {}) {
    return this.client.post<GameSnapshot>("/api/v1/games", { mode, time_control: null, ...options });
  }

  get(gameId: string) {
    return this.client.get<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}`);
  }

  move(gameId: string, command: MoveCommand) {
    return this.client.post<MoveAccepted | GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/moves`, command).then((response) => "snapshot" in response ? response.snapshot : response);
  }

  resign(gameId: string, expectedVersion: number) {
    return this.client.post<GameSnapshot>(`/api/v1/games/${encodeURIComponent(gameId)}/resign`, { expected_version: expectedVersion });
  }
}
