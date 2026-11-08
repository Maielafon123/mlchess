import type { components } from "../../../../contracts/generated/api";
import { ApiClient } from "./client";

export type AnalysisResult = components["schemas"]["AnalysisResultV1"];
export type AnalysisJob = components["schemas"]["AnalysisJobV1"];

export class AnalysisApi {
  constructor(private readonly client = new ApiClient()) {}
  request(gameId: string, ply: number, idempotencyKey: string, signal?: AbortSignal) {
    return this.client.post<AnalysisJob>(`/api/v1/games/${encodeURIComponent(gameId)}/analysis-requests`, { ply, analysis_level: "quick" }, { idempotencyKey, signal });
  }
  get(gameId: string, ply: number, signal?: AbortSignal) {
    return this.client.get<AnalysisResult | AnalysisJob>(`/api/v1/games/${encodeURIComponent(gameId)}/analysis/${ply}`, { signal });
  }
}
