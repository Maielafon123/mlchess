import { ApiClient, createIdempotencyKey } from "./client";
import type { components } from "../../../../contracts/generated/api";

/** Temporary B-016 boundary until A-018/A-019 contracts are generated. */
export type InviteSnapshot = components["schemas"]["InviteSnapshotV1"];
export type InviteState = InviteSnapshot["state"];

export class InviteApi {
  private readonly gameKey = createIdempotencyKey();
  private readonly inviteKey = createIdempotencyKey();
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  async create() {
    const game = await this.client.post<{ id: string }>("/api/v1/games", { mode: "friend", time_control: null }, { idempotencyKey: this.gameKey });
    return this.client.post<InviteSnapshot>("/api/v1/invitations", { game_id: game.id }, { idempotencyKey: this.inviteKey });
  }
  get(inviteId: string) { return this.client.get<InviteSnapshot>(`/api/v1/invitations/${encodeURIComponent(inviteId)}`); }
  accept(inviteId: string, token: string, idempotencyKey = createIdempotencyKey()) { return this.client.post<InviteSnapshot>(`/api/v1/invitations/${encodeURIComponent(inviteId)}/accept`, { token }, { idempotencyKey }); }
}
