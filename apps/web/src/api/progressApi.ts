import { ApiClient, createIdempotencyKey } from "./client";
import type { components } from "../../../../contracts/generated/api";
export type ProgressSnapshot = components["schemas"]["StudentProgressV1"];
export type SkillProgress = ProgressSnapshot["skills"][number];
export type LearningExport = components["schemas"]["LearningExportV1"];
export class ProgressApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  get(signal?: AbortSignal) { return this.client.get<ProgressSnapshot>("/api/v1/learning/progress", { signal }); }
  review(signal?: AbortSignal) { return this.client.get<ProgressSnapshot>("/api/v1/learning/review-queue", { signal }); }
  context(signal?: AbortSignal) { return this.client.get<components["schemas"]["LearningContextV1"]>("/api/v1/learning/context", { signal }); }
  export(cursor?: string) { return this.client.get<LearningExport>(`/api/v1/learning/export${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`); }
  reset(epoch: number) { return this.client.delete<void>("/api/v1/learning/data", { body: JSON.stringify({ schema_version: 1, learning_epoch: epoch, confirm: true }), headers: { "Idempotency-Key": createIdempotencyKey() } }); }
}
