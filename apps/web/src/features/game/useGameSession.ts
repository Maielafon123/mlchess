import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/errors";
import { GameApi, type GameSnapshot } from "../../api/gameApi";

type SessionState = {
  snapshot: GameSnapshot | null;
  pending: boolean;
  error: string | null;
};

function clientMoveId() {
  return globalThis.crypto?.randomUUID?.() ?? `move-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function conflictSnapshot(error: unknown): GameSnapshot | null {
  if (!(error instanceof ApiError)) return null;
  const snapshot = (error.problem as ApiError["problem"] & { snapshot?: unknown }).snapshot;
  return snapshot && typeof snapshot === "object" ? snapshot as GameSnapshot : null;
}

export function useGameSession(api?: GameApi, onAcceptedMove?: (snapshot: GameSnapshot) => void) {
  const resolvedApi = useMemo(() => api ?? new GameApi(), [api]);
  const [state, setState] = useState<SessionState>({ snapshot: null, pending: false, error: null });

  useEffect(() => {
    let cancelled = false;
    resolvedApi.create().then((snapshot) => {
      if (!cancelled) setState({ snapshot, pending: false, error: null });
    }).catch((error: unknown) => {
      if (!cancelled) setState({ snapshot: null, pending: false, error: error instanceof Error ? error.message : "Unable to create game" });
    });
    return () => { cancelled = true; };
  }, [resolvedApi]);

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
    if (!snapshot || state.pending || !snapshot.capabilities.can_resign) return;
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
