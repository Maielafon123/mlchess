import { describe, expect, it, vi } from "vitest";
import { GameWebSocket, type WebSocketLike } from "./gameWebSocket";

class FakeSocket implements WebSocketLike {
  readyState = 0;
  sent: string[] = [];
  listeners = new Map<string, Array<(event: Event | MessageEvent<string>) => void>>();
  send(value: string) { this.sent.push(value); }
  close() { this.emit("close", new Event("close")); }
  addEventListener(type: string, listener: (event: Event | MessageEvent<string>) => void) { this.listeners.set(type, [...(this.listeners.get(type) ?? []), listener]); }
  removeEventListener() {}
  emit(type: string, event: Event | MessageEvent<string>) { for (const listener of this.listeners.get(type) ?? []) listener(event); }
}

describe("GameWebSocket", () => {
  it("subscribes from after_seq and accepts only matching envelopes", () => {
    const socket = new FakeSocket();
    const onEnvelope = vi.fn();
    const client = new GameWebSocket({ url: "ws://localhost/game", gameId: "g1", afterSeq: () => 7, onEnvelope, socketFactory: () => socket });
    client.connect();
    socket.emit("open", new Event("open"));
    expect(JSON.parse(socket.sent[0])).toMatchObject({ type: "subscribe", game_id: "g1", after_seq: 7 });
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "e1", game_id: "g1", seq: 8, type: "move.accepted", occurred_at: "2026-01-01T00:00:00Z", payload: { version: 2 } }) }));
    socket.emit("message", new MessageEvent("message", { data: JSON.stringify({ schema_version: 1, event_id: "e2", game_id: "other", seq: 9, type: "move.accepted", occurred_at: "2026-01-01T00:00:00Z", payload: {} }) }));
    expect(onEnvelope).toHaveBeenCalledTimes(1);
    client.close();
  });
});
