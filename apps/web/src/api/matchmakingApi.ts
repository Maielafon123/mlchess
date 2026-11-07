import { ApiClient } from "./client";

/** Temporary B-017 boundary until A-020/A-021 contracts are generated. */
export type MatchmakingStatus = "queued" | "matched" | "cancelled" | "expired";
export type MatchTicket = { ticket_id: string; status: MatchmakingStatus; game_id: string | null; pool: string; rating_range: [number, number]; queued_at: string };
export type RatedGame = { game_id: string; status: "active" | "finished"; result: "win" | "loss" | "draw" | null; opponent: { display_name: string; rating: number }; clocks: { white_ms: number; black_ms: number; server_timestamp: string } };

export class MatchmakingApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  join(pool: string) { return this.client.post<MatchTicket>("/api/v1/matchmaking/tickets", { pool }); }
  get(ticketId: string) { return this.client.get<MatchTicket>(`/api/v1/matchmaking/tickets/${encodeURIComponent(ticketId)}`); }
  cancel(ticketId: string) { return this.client.post<MatchTicket>(`/api/v1/matchmaking/tickets/${encodeURIComponent(ticketId)}/cancel`, {}); }
  game(gameId: string) { return this.client.get<RatedGame>(`/api/v1/games/${encodeURIComponent(gameId)}`); }
  resign(gameId: string) { return this.client.post<RatedGame>(`/api/v1/games/${encodeURIComponent(gameId)}/resign`, {}); }
  offerDraw(gameId: string) { return this.client.post<RatedGame>(`/api/v1/games/${encodeURIComponent(gameId)}/draw-offer`, {}); }
}
