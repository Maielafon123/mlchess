import { ApiClient, createIdempotencyKey } from "./client";
import type { components } from "../../../../contracts/generated/api";

/** Temporary B-016 boundary until A-018/A-019 contracts are generated. */
export type InviteSnapshot = components["schemas"]["InviteSnapshotV1"];
export type InviteState = InviteSnapshot["state"];
export type TimeControl = components["schemas"]["TimeControlV1"];

export class InviteApi {
  private creation: { preset: string; gameKey: string; inviteKey: string } | null = null;
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  async create(timeControl: TimeControl | null = null) {
    const preset = timeControl ? `${timeControl.initial_ms}:${timeControl.increment_ms}` : "untimed";
    if (this.creation?.preset !== preset) this.creation = { preset, gameKey: createIdempotencyKey(), inviteKey: createIdempotencyKey() };
    const { gameKey, inviteKey } = this.creation;
    const game = await this.client.post<{ id: string }>("/api/v1/games", { mode: "friend", time_control: timeControl }, { idempotencyKey: gameKey });
    return this.client.post<InviteSnapshot>("/api/v1/invitations", { game_id: game.id }, { idempotencyKey: inviteKey });
  }
  get(inviteId: string) { return this.client.get<InviteSnapshot>(`/api/v1/invitations/${encodeURIComponent(inviteId)}`); }
  accept(inviteId: string, token: string, idempotencyKey = createIdempotencyKey()) { return this.client.post<InviteSnapshot>(`/api/v1/invitations/${encodeURIComponent(inviteId)}/accept`, { token }, { idempotencyKey }); }
}
