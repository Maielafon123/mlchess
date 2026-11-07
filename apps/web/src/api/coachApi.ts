import { ApiClient } from "./client";

export type CoachLevel = "observation" | "direction" | "idea" | "candidates" | "solution";
export type CoachRequest = { schema_version: 1; game_id: string; analysis_id: string; revision: number; ply: number; language: "ru" | "en"; level: CoachLevel };
export type CoachExplanation = { schema_version: 1; game_id: string; revision: number; ply: number; analysis_id: string; language: "ru" | "en"; level: CoachLevel; summary: string; why: string; question: string; referenced_uci: string[]; highlight_squares: string[]; claim_refs: string[]; template_id: string; confidence: "grounded" | "uncertain" | "fallback"; model_id: string; prompt_version: string; fallback_used: boolean };
export type CoachJob = { job_id: string; status: "pending" | "ready"; explanation: CoachExplanation | null; failure_code?: string | null };

export class CoachApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  request(body: CoachRequest) { return this.client.post<CoachJob>("/api/v1/coach-requests", body); }
  get(jobId: string) { return this.client.get<CoachJob>(`/api/v1/coach-requests/${encodeURIComponent(jobId)}`); }
}
