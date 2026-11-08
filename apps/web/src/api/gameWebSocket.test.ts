import { afterEach, describe, expect, it, vi } from "vitest";
import { GameWebSocket, type WebSocketLike } from "./gameWebSocket";

class FakeSocket implements WebSocketLike {
  readyState = 0;
  sent: string[] = [];
  listeners = new Map<string, Array<(event: Event | MessageEvent<string>) => void>>();
  send(value: string) { this.sent.push(value); }
  close() { this.emit("close", new Event("close")); }
  addEventListener(type: string, listener: (event: Event | MessageEvent<string>) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
  removeEventListener(type: string, listener: (event: Event | MessageEvent<string>) => void) { this.listeners.set(type, (this.listeners.get(type) ?? []).filter((item) => item !== listener)); }
  emit(type: string, event: Event | MessageEvent<string>) { for (const listener of this.listeners.get(type) ?? []) listener(event); }
}

describe("GameWebSocket", () => {
  afterEach(() => vi.useRealTimers());
  it("subscribes from after_seq and accepts only matching envelopes", () => {
    const socket = new FakeSocket();
    const onEnvelope = vi.fn();
    const client = new GameWebSocket({ url: "ws://localhost/game", gameId: "g1", afterSeq: () => 7, onEnvelope, socketFactory: () => socket });
    client.connect();
    socket.emit("open", new Event("open"));
    expect(JSON.parse(socket.sent[0])).toMatchObject({ type: "subscribe", game_id: "g1", after_seq: 7 });
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "e1", game_id: "g1", seq: 8, type: "game.move_committed", occurred_at: "2026-01-01T00:00:00Z", payload: { version: 2 } }) }));
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "e2", game_id: "other", seq: 9, type: "game.move_committed", occurred_at: "2026-01-01T00:00:00Z", payload: {} }) }));
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "e3", game_id: "g1", seq: 10, type: "move.accepted", occurred_at: "2026-01-01T00:00:00Z", payload: {} }) }));
    expect(onEnvelope).toHaveBeenCalledTimes(1);
    client.close();
    expect(Array.from(socket.listeners.values()).flat()).toHaveLength(0);
  });

  it("bounds retries even when rejected sockets open then immediately close", () => {
    vi.useFakeTimers();
    const sockets: FakeSocket[] = [];
    const client = new GameWebSocket({ url: "ws://localhost/game", gameId: "g1", afterSeq: () => 0, maxRetries: 2, onEnvelope: vi.fn(), socketFactory: () => { const socket = new FakeSocket(); sockets.push(socket); return socket; } });
    client.connect();
    for (let index = 0; index < 3; index += 1) {
      sockets[index].emit("open", new Event("open"));
      sockets[index].emit("close", new CloseEvent("close", { code: 1006 }));
      vi.runOnlyPendingTimers();
    }
    expect(sockets).toHaveLength(3);
    client.close();
  });

  it("does not reconnect a revoked session and ignores detached socket messages", () => {
    vi.useFakeTimers();
    const socket = new FakeSocket();
    const onEnvelope = vi.fn();
    const factory = vi.fn(() => socket);
    const client = new GameWebSocket({ url: "ws://localhost/game", gameId: "g1", afterSeq: () => 0, onEnvelope, socketFactory: factory });
    client.connect();
    socket.emit("open", new Event("open"));
    socket.emit("close", new CloseEvent("close", { code: 4401 }));
    vi.runAllTimers();
    expect(factory).toHaveBeenCalledTimes(1);
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "late", game_id: "g1", seq: 1, type: "game.snapshot", occurred_at: "2026-01-01T00:00:00Z", payload: {} }) }));
    expect(onEnvelope).not.toHaveBeenCalled();
    client.close();
  });
});
