import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { WsStateAdapter } from "./wsStateAdapter";
import type { WsEnvelope } from "./wsEnvelope";

type Snapshot = { count: number };
type Payload = { delta: number };

const event = (seq: number, delta: number): WsEnvelope<Payload> => ({
  schema_version: 1,
  event_id: `event-${seq}`,
  game_id: "mock-game-0001",
  seq,
  type: "mock.delta",
  occurred_at: "2026-11-07T12:00:00Z",
  payload: { delta },
});

describe("WsStateAdapter", () => {
  it("updates Query data only for accepted contiguous events", async () => {
    const queryClient = new QueryClient();
    const key = ["mock-game"];
    queryClient.setQueryData<Snapshot>(key, { count: 0 });
    const resync = vi.fn(async () => ({ snapshot: { count: 10 }, seq: 2 }));
    const adapter = new WsStateAdapter<Snapshot, Payload>({
      queryClient,
      queryKey: key,
      resync,
      reduceEvent: (snapshot, current) => ({ count: snapshot.count + current.payload.delta }),
    });

    expect(await adapter.ingest(event(1, 1))).toBe("accepted");
    expect(await adapter.ingest(event(1, 1))).toBe("duplicate");
    expect(queryClient.getQueryData<Snapshot>(key)).toEqual({ count: 1 });
    expect(resync).not.toHaveBeenCalled();
  });

  it("resyncs through REST on a sequence gap, then resumes events", async () => {
    const queryClient = new QueryClient();
    const key = ["mock-game"];
    queryClient.setQueryData<Snapshot>(key, { count: 0 });
    const resync = vi.fn(async () => ({ snapshot: { count: 10 }, seq: 2 }));
    const adapter = new WsStateAdapter<Snapshot, Payload>({
      queryClient,
      queryKey: key,
      resync,
      reduceEvent: (snapshot, current) => ({ count: snapshot.count + current.payload.delta }),
    });

    expect(await adapter.ingest(event(2, 1))).toBe("resync_required");
    expect(queryClient.getQueryData<Snapshot>(key)).toEqual({ count: 10 });
    expect(adapter.afterSeq).toBe(2);
    expect(adapter.resyncRequired).toBe(false);
    expect(resync).toHaveBeenCalledOnce();
    expect(await adapter.ingest(event(3, 2))).toBe("accepted");
    expect(queryClient.getQueryData<Snapshot>(key)).toEqual({ count: 12 });
  });
});
