export type WsEnvelope<TPayload> = {
  schema_version: number;
  event_id: string;
  game_id: string;
  seq: number;
  type: string;
  occurred_at: string;
  payload: TPayload;
};

export type IngestResult = "accepted" | "duplicate" | "resync_required";

/** Client-only ordering boundary; authoritative state is always fetched via REST. */
export class WsEventStore<TPayload> {
  private latestSequence = 0;
  private needsResync = false;

  get afterSeq() {
    return this.latestSequence;
  }

  get resyncRequired() {
    return this.needsResync;
  }

  ingest(event: WsEnvelope<TPayload>): IngestResult {
    if (event.seq <= this.latestSequence) return "duplicate";
    if (event.seq !== this.latestSequence + 1) {
      this.needsResync = true;
      return "resync_required";
    }
    this.latestSequence = event.seq;
    return "accepted";
  }

  markResynced(snapshotSequence: number) {
    if (!Number.isInteger(snapshotSequence) || snapshotSequence < 0) {
      throw new Error("snapshotSequence must be a non-negative integer");
    }
    this.latestSequence = snapshotSequence;
    this.needsResync = false;
  }
}
