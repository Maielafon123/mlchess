import { describe, expect, it } from "vitest";
import { WsEventStore, type WsEnvelope } from "./wsEnvelope";

const event = (seq: number): WsEnvelope<{ kind: string }> => ({
  schema_version: 1,
  event_id: `event-${seq}`,
  game_id: "mock-game-0001",
  seq,
  type: "mock.event",
  occurred_at: "2026-11-07T12:00:00Z",
  payload: { kind: "fixture" },
});

describe("WsEventStore", () => {
  it("accepts contiguous events and ignores duplicates", () => {
    const store = new WsEventStore();
    expect(store.ingest(event(1))).toBe("accepted");
    expect(store.ingest(event(1))).toBe("duplicate");
    expect(store.afterSeq).toBe(1);
  });

  it("requests REST resync when a sequence gap appears", () => {
    const store = new WsEventStore();
    expect(store.ingest(event(2))).toBe("resync_required");
    expect(store.resyncRequired).toBe(true);
    store.markResynced(2);
    expect(store.resyncRequired).toBe(false);
    expect(store.ingest(event(3))).toBe("accepted");
  });
});
