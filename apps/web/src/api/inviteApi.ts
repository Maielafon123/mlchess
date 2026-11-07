import { ApiClient } from "./client";

/** Temporary B-016 boundary until A-018/A-019 contracts are generated. */
export type InviteState = "waiting" | "active" | "expired" | "full";
export type InviteSnapshot = { invite_id: string; game_id: string | null; state: InviteState; invite_url: string; opponent: { display_name: string; connected: boolean } | null; clocks: { white_ms: number; black_ms: number; server_timestamp: string } | null };

export class InviteApi {
  constructor(private readonly client: ApiClient = new ApiClient()) {}
  create() { return this.client.post<InviteSnapshot>("/api/v1/invites", { mode: "friend" }); }
  get(inviteId: string) { return this.client.get<InviteSnapshot>(`/api/v1/invites/${encodeURIComponent(inviteId)}`); }
  accept(inviteId: string) { return this.client.post<InviteSnapshot>(`/api/v1/invites/${encodeURIComponent(inviteId)}/accept`, {}); }
}
