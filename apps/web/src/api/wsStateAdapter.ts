import type { QueryClient, QueryKey } from "@tanstack/react-query";
import { WsEventStore, type IngestResult, type WsEnvelope } from "./wsEnvelope";

export type SnapshotResync<TSnapshot> = {
  snapshot: TSnapshot;
  seq: number;
};

export type EventReducer<TSnapshot, TPayload> = (
  snapshot: TSnapshot,
  event: WsEnvelope<TPayload>,
) => TSnapshot;

export type WsStateAdapterOptions<TSnapshot, TPayload> = {
  queryClient: QueryClient;
  queryKey: QueryKey;
  resync: () => Promise<SnapshotResync<TSnapshot>>;
  reduceEvent: EventReducer<TSnapshot, TPayload>;
};

/**
 * Bridges transport ordering to TanStack Query without owning domain rules.
 * A sequence gap always triggers the supplied REST snapshot resync callback.
 */
export class WsStateAdapter<TSnapshot, TPayload> {
  private readonly queryClient: QueryClient;
  private readonly queryKey: QueryKey;
  private readonly resync: WsStateAdapterOptions<TSnapshot, TPayload>["resync"];
  private readonly reduceEvent: EventReducer<TSnapshot, TPayload>;
  private readonly eventStore = new WsEventStore<TPayload>();

  constructor({ queryClient, queryKey, resync, reduceEvent }: WsStateAdapterOptions<TSnapshot, TPayload>) {
    this.queryClient = queryClient;
    this.queryKey = queryKey;
    this.resync = resync;
    this.reduceEvent = reduceEvent;
  }

  get afterSeq() {
    return this.eventStore.afterSeq;
  }

  get resyncRequired() {
    return this.eventStore.resyncRequired;
  }

  async ingest(event: WsEnvelope<TPayload>): Promise<IngestResult> {
    const result = this.eventStore.ingest(event);
    if (result === "duplicate") return result;

    if (result === "accepted") {
      this.queryClient.setQueryData<TSnapshot>(this.queryKey, (snapshot) => {
        if (snapshot === undefined) return snapshot;
        return this.reduceEvent(snapshot, event);
      });
      return result;
    }

    const refreshed = await this.resync();
    this.queryClient.setQueryData(this.queryKey, refreshed.snapshot);
    this.eventStore.markResynced(refreshed.seq);
    return result;
  }
}
