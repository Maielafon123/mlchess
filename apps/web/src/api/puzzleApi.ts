import { ApiClient, createIdempotencyKey } from "./client";
import type { Language } from "./learningApi";
import type { components } from "../../../../contracts/generated/api";

export type Puzzle = components["schemas"]["PuzzleV1"];
export type PuzzleState = components["schemas"]["PuzzleStateV1"];
export type PuzzleAttempt = components["schemas"]["PuzzleAttemptV1"];
type PuzzleList = components["schemas"]["PuzzleListV1"];
type AttemptRequest = components["schemas"]["PuzzleAttemptRequestV1"];
const path = (id: string) => `/api/v1/learning/puzzles/${encodeURIComponent(id)}`;
export class PuzzleApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  list(signal?: AbortSignal) { return this.client.get<PuzzleList>("/api/v1/learning/puzzles", { signal }); }
  get(id: string, signal?: AbortSignal) { return this.client.get<Puzzle>(path(id), { signal }); }
  state(id: string, language: Language = "ru", signal?: AbortSignal) { return this.client.get<PuzzleState>(`${path(id)}/state?language=${language}`, { signal }); }
  attempt(id: string, uci: string, state: PuzzleState, attemptId = createIdempotencyKey()) {
    const body: AttemptRequest = { schema_version: 1, learning_epoch: state.learning_epoch, uci, attempt_id: attemptId, session_number: state.session_number, expected_ply: state.next_ply };
    return this.client.post<PuzzleAttempt>(`${path(id)}/attempts`, body, { idempotencyKey: attemptId });
  }
  hint(id: string, state: PuzzleState, language: Language = "ru", commandKey = createIdempotencyKey()) {
    return this.client.post<components["schemas"]["PuzzleHintV1"]>(`${path(id)}/hints?language=${language}`, { schema_version: 1, learning_epoch: state.learning_epoch, session_number: state.session_number }, { idempotencyKey: commandKey });
  }
  restart(id: string, state: PuzzleState, language: Language = "ru", commandKey = createIdempotencyKey()) {
    return this.client.post<PuzzleState>(`${path(id)}/restart?language=${language}`, { schema_version: 1, learning_epoch: state.learning_epoch, session_number: state.session_number }, { idempotencyKey: commandKey });
  }
}
