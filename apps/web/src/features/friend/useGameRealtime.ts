import { useEffect, useState } from "react";
import { GameWebSocket } from "../../api/gameWebSocket";
import { WsEventStore } from "../../api/wsEnvelope";
import type { GameApi, GameSnapshot } from "../../api/gameApi";

export function useGameRealtime(gameId: string | undefined, api: GameApi, onSnapshot: (snapshot: GameSnapshot) => void) {
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    if (!gameId || !/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(gameId) || typeof WebSocket === "undefined") return;
    let active = true;
    let cursor = new WsEventStore<unknown>();
    let refreshing = false;
    let dirty = false;
    let fresh = false;
    const url = new URL(`/ws/v1/games/${gameId}`, window.location.href);
    url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
    const refresh = async () => {
      dirty = true;
      if (refreshing) return;
      refreshing = true;
      try {
        while (active && dirty) {
          dirty = false;
          const next = await api.get(gameId);
          if (active) onSnapshot(next);
        }
      } catch { if (active) setConnected(false); }
      finally { refreshing = false; }
    };
    const transport = new GameWebSocket<unknown>({
      url: url.toString(), gameId,
      afterSeq: () => fresh ? 0 : cursor.afterSeq,
      onState: (status) => { if (active && status !== "open") setConnected(false); },
      onEnvelope: (frame) => {
        if (!active) return;
        // Controls precede durable ordering. REST never supplies an event cursor.
        if (frame.type === "game.snapshot") {
          const snapshot = frame.payload as GameSnapshot | null;
          if (!snapshot || snapshot.id !== gameId || snapshot.schema_version !== 1 || !Number.isSafeInteger(snapshot.version) || !Array.isArray(snapshot.moves)) return;
          cursor.markResynced(frame.seq); fresh = false;
          onSnapshot(snapshot); setConnected(true);
          return;
        }
        if (frame.type === "server.resync_required") {
          fresh = true; cursor = new WsEventStore();
          setConnected(false); void refresh();
          // The server closes with1012. Reconnect requests a fresh atomic pair.
          return;
        }
        if (fresh) return;
        const result = cursor.ingest(frame);
        if (result === "resync_required") {
          fresh = true; setConnected(false);
          transport.close(); transport.connect();
        }
        if (result === "accepted") setConnected(true);
        if (result !== "duplicate") void refresh();
      },
    });
    transport.connect();
    const navigating = () => transport.close();
    const resume = () => { if (active) { fresh = true; transport.close(); transport.connect(); void refresh(); } };
    const visible = () => { if (!document.hidden) resume(); };
    window.addEventListener("pagehide", navigating);
    window.addEventListener("pageshow", resume);
    document.addEventListener("visibilitychange", visible);
    return () => {
      active = false; transport.close();
      window.removeEventListener("pagehide", navigating);
      window.removeEventListener("pageshow", resume);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [gameId, api, onSnapshot]);
  return connected;
}
