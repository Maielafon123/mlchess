import { ApiClient } from "./client";
import type { components } from "../../../../contracts/generated/api";

export type CoachRequest = components["schemas"]["CoachRequestV1"];
export type CoachLevel = CoachRequest["level"];
export type CoachExplanation = components["schemas"]["CoachExplanationV1"];
export type CoachJob = components["schemas"]["CoachJobV1"];

export class CoachApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  request(body: CoachRequest) { return this.client.post<CoachJob>(`/api/v1/games/${encodeURIComponent(body.game_id)}/coach-requests`, body); }
  get(gameId: string, jobId: string) { return this.client.get<CoachJob>(`/api/v1/games/${encodeURIComponent(gameId)}/coach-requests/${encodeURIComponent(jobId)}`); }
}
