import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError } from "../../api/errors";
import { GameApi, canAdoptSnapshot, type GameSnapshot } from "../../api/gameApi";
import { createIdempotencyKey } from "../../api/client";
import { ensurePublicSession } from "../../auth/guestSession";
import { useHumanGameActions } from "./useHumanGameActions";

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
  const resume = useMemo(() => ({ mode, id: new URLSearchParams(window.location.search).get("game") }), [mode]);
  const [state, setState] = useState<SessionState>({ snapshot: null, pending: false, error: null });
  const adopt = useCallback((next: GameSnapshot) => {
    setState((current) => current.snapshot && canAdoptSnapshot(current.snapshot, next)
      ? { ...current, snapshot: next, error: null } : current);
  }, []);
  const actions = useHumanGameActions(state.snapshot, resolvedApi, adopt, state.pending);
  const pending = state.pending || actions.pending;

  useEffect(() => {
    let cancelled = false;
    ensurePublicSession().then(() => resume.id ? resolvedApi.get(resume.id) : resolvedApi.create(mode, undefined, creationKey)).then((snapshot) => {
      if (snapshot.mode !== mode) throw new Error("Это ссылка на другой режим игры.");
      if (!cancelled) {
        window.history.replaceState(window.history.state, "", `/play/${mode}?game=${encodeURIComponent(snapshot.id)}`);
        setState({ snapshot, pending: false, error: null });
      }
    }).catch((error: unknown) => {
      if (!cancelled) setState({ snapshot: null, pending: false, error: error instanceof Error ? error.message : "Unable to create game" });
    });
    return () => { cancelled = true; };
  }, [resolvedApi, mode, creationKey, resume]);

  const gameId = state.snapshot?.id;
  const timedActive = state.snapshot?.status === "active" && !!state.snapshot.clock;
  const enginePending = state.snapshot?.status === "active" && state.snapshot.players.some(
    (player) => player.kind === "engine" && player.side === state.snapshot?.side_to_move);
  useEffect(() => {
    if (!gameId || (!enginePending && !timedActive) || pending) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const next = await resolvedApi.get(gameId);
        if (!cancelled) setState((current) => current.snapshot?.id === gameId && canAdoptSnapshot(current.snapshot, next)
          ? { ...current, snapshot: next, error: null } : current);
      } catch (error: unknown) {
        if (!cancelled) setState((current) => ({ ...current, error: error instanceof Error ? error.message : "Unable to refresh game" }));
      } finally {
        if (!cancelled) timer = setTimeout(poll, 1000);
      }
    };
    timer = setTimeout(poll, 500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [enginePending, gameId, pending, resolvedApi, timedActive]);

  const move = useCallback(async (uci: string) => {
    const snapshot = state.snapshot;
    if (!snapshot || pending || !snapshot.capabilities.can_move) return;
    setState((current) => ({ ...current, pending: true, error: null }));
    try {
      const next = await resolvedApi.move(snapshot.id, { uci, client_move_id: clientMoveId(), expected_version: snapshot.version });
      setState({ snapshot: next, pending: false, error: null });
      onAcceptedMove?.(next);
    } catch (error: unknown) {
      const rollback = conflictSnapshot(error);
      setState((current) => ({ snapshot: rollback ?? current.snapshot, pending: false, error: error instanceof Error ? error.message : "Move rejected" }));
    }
  }, [onAcceptedMove, pending, resolvedApi, state.snapshot]);

  return { ...state, pending, error: actions.error ?? state.error, actions, move };
}
