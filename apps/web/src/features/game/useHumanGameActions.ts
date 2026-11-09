import { useEffect, useRef, useState } from "react";
import { createIdempotencyKey } from "../../api/client";
import type { GameActions, GameApi, GameSnapshot, HumanAction } from "../../api/gameApi";

export function useHumanGameActions(game: GameSnapshot | null, api: GameApi, adopt: (next: GameSnapshot) => void, suspended = false) {
  const [capabilities, setCapabilities] = useState<GameActions | null>(null);
  const [pendingFor, setPendingFor] = useState<string | null>(null);
  const [error, setError] = useState<{ gameId: string; message: string } | null>(null);
  const operation = useRef<symbol | null>(null);
  const gameId = game?.id;
  const version = game?.version;
  const active = game?.status === "active";
  useEffect(() => () => { operation.current = null; }, [gameId]);
  useEffect(() => {
    if (!gameId || !active) return;
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const next = await api.actions(gameId, abort.signal);
        if (!abort.signal.aborted) setCapabilities(next);
      } catch {
        if (!abort.signal.aborted) timer = setTimeout(refresh, 1500);
      }
    };
    void refresh();
    return () => { abort.abort(); clearTimeout(timer); };
  }, [active, api, gameId, version]);
  const send = async (action: HumanAction | "move", uci?: string) => {
    if (!game || !active || suspended || operation.current || (action === "move" && (!uci || !game.capabilities.can_move))) return;
    const marker = Symbol();
    operation.current = marker;
    setPendingFor(game.id); setError(null);
    try {
      const key = createIdempotencyKey();
      const next = await (action === "move" ? api.move(game.id, { uci: uci!, client_move_id: key, expected_version: game.version }) : api.action(game.id, action, game.version, key));
      if (operation.current === marker) adopt(next);
    } catch (failure) {
      if (operation.current !== marker) return;
      setError({ gameId: game.id, message: failure instanceof Error ? failure.message : "Не удалось выполнить действие." });
      try {
        const next = await api.get(game.id);
        if (operation.current === marker) adopt(next);
      } catch { /* Realtime and the fallback poll can recover. */ }
    } finally {
      if (operation.current === marker) { operation.current = null; setPendingFor(null); }
    }
  };
  return {
    capabilities: capabilities?.game_id === gameId && capabilities?.version === version ? capabilities : null,
    pending: !!gameId && pendingFor === gameId,
    error: error?.gameId === gameId ? error?.message ?? null : null,
    move: (uci: string) => void send("move", uci),
    action: (kind: HumanAction) => void send(kind),
  };
}
