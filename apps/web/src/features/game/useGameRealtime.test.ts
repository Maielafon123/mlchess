import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useGameRealtime } from "./useGameRealtime";
import gameFixture from "../../../../../contracts/fixtures/game/snapshot-coach.json";
import type { GameApi } from "../../api/gameApi";

const gameId = "00000000-0000-4000-8000-000000000001";
const sockets: Socket[] = [];
class Socket extends EventTarget {
  readyState = 0;
  sent: Array<{ after_seq: number }> = [];
  constructor(_url: string) { super(); sockets.push(this); }
  send(data: string) { this.sent.push(JSON.parse(data)); }
  close() { this.dispatchEvent(new CloseEvent("close", { code: 1000 })); }
  open() { this.dispatchEvent(new Event("open")); }
  frame(type: string, seq: number, payload: unknown) { this.dispatchEvent(new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: crypto.randomUUID(), game_id: gameId, seq, type, occurred_at: "2026-11-09T00:00:00Z", payload }) })); }
}

describe("useGameRealtime", () => {
  afterEach(() => { vi.unstubAllGlobals(); sockets.length = 0; });
  it("handles controls before ordering, and a gap reconnects from an atomic snapshot", async () => {
    vi.stubGlobal("WebSocket", Socket);
    const snapshot = { ...gameFixture, id: gameId, version: 1 };
    const api = { get: vi.fn().mockResolvedValue(snapshot) } as unknown as GameApi;
    const onSnapshot = vi.fn();
    const { result, unmount } = renderHook(() => useGameRealtime(gameId, api, onSnapshot));
    act(() => { sockets[0].open(); sockets[0].frame("game.snapshot", 8, snapshot); });
    expect(sockets[0].sent[0].after_seq).toBe(0);
    expect(result.current).toBe(true);
    expect(onSnapshot).toHaveBeenCalledWith(snapshot);
    act(() => sockets[0].frame("game.move_committed", 10, { version: 2 }));
    expect(sockets).toHaveLength(2);
    act(() => sockets[1].open());
    expect(sockets[1].sent[0].after_seq).toBe(0);
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(onSnapshot).toHaveBeenCalledTimes(2));
    const delivered = onSnapshot.mock.calls.length;
    act(() => sockets[0].frame("game.snapshot", 1, { ...snapshot, version: 0 }));
    expect(onSnapshot).toHaveBeenCalledTimes(delivered);
    unmount();
  });
});
