import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/errors";
import { GameApi, type GameSnapshot } from "../../api/gameApi";
import { createIdempotencyKey } from "../../api/client";

type SessionState = {
  snapshot: GameSnapshot | null;
  pending: boolean;
  error: string | null;
};

function clientMoveId() {
  return createIdempotencyKey();
}

function conflictSnapshot(error: unknown): GameSnapshot | null {
  if (!(error instanceof ApiError)) return null;
  const snapshot = (error.problem as ApiError["problem"] & { snapshot?: unknown }).snapshot;
  return snapshot && typeof snapshot === "object" ? snapshot as GameSnapshot : null;
}

export function useGameSession(api?: GameApi, onAcceptedMove?: (snapshot: GameSnapshot) => void, mode: "ai" | "coach" = "ai") {
  const resolvedApi = useMemo(() => api ?? new GameApi(), [api]);
  const creationKey = useMemo(() => ({ mode, key: createIdempotencyKey() }), [mode]).key;
  const [state, setState] = useState<SessionState>({ snapshot: null, pending: false, error: null });

  useEffect(() => {
    let cancelled = false;
    resolvedApi.create(mode, undefined, creationKey).then((snapshot) => {
      if (!cancelled) setState({ snapshot, pending: false, error: null });
    }).catch((error: unknown) => {
      if (!cancelled) setState({ snapshot: null, pending: false, error: error instanceof Error ? error.message : "Unable to create game" });
    });
    return () => { cancelled = true; };
  }, [resolvedApi, mode, creationKey]);

  const gameId = state.snapshot?.id;
  const enginePending = state.snapshot?.status === "active" && state.snapshot.players.some(
    (player) => player.kind === "engine" && player.side === state.snapshot?.side_to_move);
  useEffect(() => {
    if (!gameId || !enginePending || state.pending) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await resolvedApi.get(gameId);
        if (!cancelled) setState((current) => current.snapshot?.id === gameId && next.version >= current.snapshot.version
          ? { ...current, snapshot: next, error: null } : current);
      } catch (error: unknown) {
        if (!cancelled) setState((current) => ({ ...current, error: error instanceof Error ? error.message : "Unable to refresh game" }));
      } finally {
        if (!cancelled) timer = setTimeout(poll, 1000);
      }
    };
    timer = setTimeout(poll, 500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [enginePending, gameId, resolvedApi, state.pending]);

  const move = useCallback(async (uci: string) => {
    const snapshot = state.snapshot;
    if (!snapshot || state.pending || !snapshot.capabilities.can_move) return;
    setState((current) => ({ ...current, pending: true, error: null }));
    try {
      const next = await resolvedApi.move(snapshot.id, { uci, client_move_id: clientMoveId(), expected_version: snapshot.version });
      setState({ snapshot: next, pending: false, error: null });
      onAcceptedMove?.(next);
    } catch (error: unknown) {
      const rollback = conflictSnapshot(error);
      setState((current) => ({ snapshot: rollback ?? current.snapshot, pending: false, error: error instanceof Error ? error.message : "Move rejected" }));
    }
  }, [onAcceptedMove, resolvedApi, state.pending, state.snapshot]);

  const resign = useCallback(async () => {
    const snapshot = state.snapshot;
    if (!snapshot || state.pending || snapshot.status !== "active") return;
    setState((current) => ({ ...current, pending: true, error: null }));
    try {
      const next = await resolvedApi.resign(snapshot.id, snapshot.version);
      setState({ snapshot: next, pending: false, error: null });
    } catch (error: unknown) {
      setState((current) => ({ ...current, pending: false, error: error instanceof Error ? error.message : "Resign rejected" }));
    }
  }, [resolvedApi, state.pending, state.snapshot]);

  return useMemo(() => ({ ...state, move, resign }), [move, resign, state]);
}
