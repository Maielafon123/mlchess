import { ApiClient, createIdempotencyKey } from "./client";
import type { components } from "../../../../contracts/generated/api";

type Schemas = components["schemas"];
export type MatchTicket = Schemas["MatchTicketV1"];
export type RatedGame = Schemas["RatedGameV1"];
export type RatingPool = Schemas["RatingPoolV1"];
export type MatchPool = Schemas["MatchPoolV1"];
const path = (id: string) => `/api/v1/matchmaking/tickets/${encodeURIComponent(id)}`;

export class MatchmakingApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  pools(signal?: AbortSignal) { return this.client.get<Schemas["MatchPoolsV1"]>("/api/v1/matchmaking/pools", { signal }); }
  current(signal?: AbortSignal) { return this.client.get<Schemas["CurrentMatchV1"]>("/api/v1/matchmaking/current", { signal }); }
  join(pool: RatingPool, idempotencyKey = createIdempotencyKey()) {
    return this.client.post<MatchTicket>("/api/v1/matchmaking/tickets", { schema_version: 1, pool }, { idempotencyKey });
  }
  get(ticketId: string, signal?: AbortSignal) { return this.client.get<MatchTicket>(path(ticketId), { signal }); }
  cancel(ticketId: string, idempotencyKey = createIdempotencyKey()) {
    return this.client.delete<MatchTicket>(path(ticketId), { headers: { "Idempotency-Key": idempotencyKey } });
  }
  game(gameId: string, signal?: AbortSignal) { return this.client.get<RatedGame>(`/api/v1/games/${encodeURIComponent(gameId)}/rating`, { signal }); }
}
