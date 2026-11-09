import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AiGameApi, aiView, type AiGameOptions, type AiGameSnapshot } from "../../api/aiGameApi";
import { createIdempotencyKey } from "../../api/client";
import { ensurePublicSession } from "../../auth/guestSession";
import { canAdoptSnapshot } from "../../api/gameApi";

export type AiOperation = "creating" | "moving" | "takeback" | "engine" | null;
export type AiSessionState = { snapshot: AiGameSnapshot | null; pending: AiOperation; error: string | null };

/** Ignore a delayed engine response once a newer operation has changed the branch. */
export function acceptsEngineResult(activeRequestId: number, resultRequestId: number, activeVersion: number, resultVersion: number) {
  return activeRequestId === resultRequestId && resultVersion >= activeVersion;
}

function commandId() {
  return createIdempotencyKey();
}

export function useAiGameSession(options: AiGameOptions, api?: AiGameApi) {
  const resolvedApi = useMemo(() => api ?? new AiGameApi(), [api]);
  const creation = useMemo(() => ({ key: createIdempotencyKey(), resume: (() => {
    const query = new URLSearchParams(window.location.search);
    return query.get("profile") === options.profile_id && query.get("side") === options.side ? query.get("game") : null;
  })(), options: {
    ...options, side: options.side === "random"
      ? (globalThis.crypto.getRandomValues(new Uint8Array(1))[0] % 2 === 0 ? "white" as const : "black" as const) : options.side,
  } }), [options]);
  const requestId = useRef(0);
  const [state, setState] = useState<AiSessionState>({ snapshot: null, pending: "creating", error: null });

  useEffect(() => {
    const id = ++requestId.current;
    setState({ snapshot: null, pending: "creating", error: null });
    ensurePublicSession().then(() => creation.resume ? resolvedApi.get(creation.resume) : resolvedApi.createAi(creation.options, creation.key)).then((wire) => {
      if (wire.mode !== "ai") throw new Error("Это ссылка на другой режим игры.");
      const snapshot = aiView(wire, options.profile_id);
      if (id === requestId.current) {
        const query = new URLSearchParams({ game: snapshot.id, profile: options.profile_id, side: snapshot.player_side });
        window.history.replaceState(window.history.state, "", "/play/ai?" + query.toString());
        setState({ snapshot, pending: snapshot.engine_pending ? "engine" : null, error: null });
      }
    }).catch((error: unknown) => {
      if (id === requestId.current) setState({ snapshot: null, pending: null, error: error instanceof Error ? error.message : "Unable to create AI game" });
    });
    return () => { requestId.current += 1; };
  }, [creation, options.profile_id, resolvedApi]);

  const gameId = state.snapshot?.id;
  const timedActive = state.snapshot?.status === "active" && !!state.snapshot.clock;
  useEffect(() => {
    if (!gameId || (state.pending !== "engine" && !(timedActive && state.pending === null))) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const id = requestId.current;
    const poll = async () => {
      try {
        const next = aiView(await resolvedApi.get(gameId), options.profile_id);
        if (!cancelled && id === requestId.current) {
          setState((current) => canAdoptSnapshot(current.snapshot, next)
            ? { snapshot: next, pending: next.engine_pending ? "engine" : null, error: null } : current);
        }
      } catch (error: unknown) {
        if (!cancelled && id === requestId.current) setState((current) => ({ ...current, error: error instanceof Error ? error.message : "Unable to refresh game" }));
      } finally {
        if (!cancelled) timer = setTimeout(poll, 1000);
      }
    };
    timer = setTimeout(poll, 500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [gameId, options.profile_id, resolvedApi, state.pending, timedActive]);

  const recover = useCallback(async (gameId: string, id: number, error: unknown) => {
    const message = error instanceof Error ? error.message : "Обновляем позицию…";
    try {
      const snapshot = aiView(await resolvedApi.get(gameId), options.profile_id);
      if (id === requestId.current) setState({ snapshot, pending: snapshot.engine_pending ? "engine" : null, error: message });
    } catch {
      if (id === requestId.current) setState((current) => ({ ...current, pending: current.snapshot?.engine_pending ? "engine" : null, error: message }));
    }
  }, [options.profile_id, resolvedApi]);

  const move = useCallback(async (uci: string) => {
    const snapshot = state.snapshot;
    if (!snapshot || state.pending || !snapshot.capabilities.can_move) return;
    const id = ++requestId.current;
    setState((current) => ({ ...current, pending: "moving", error: null }));
    try {
      const next = aiView(await resolvedApi.move(snapshot.id, { uci, client_move_id: commandId(), expected_version: snapshot.version }), options.profile_id);
      if (!acceptsEngineResult(requestId.current, id, snapshot.version, next.version)) return;
      setState({ snapshot: next, pending: next.engine_pending ? "engine" : null, error: null });
    } catch (error: unknown) {
      await recover(snapshot.id, id, error);
    }
  }, [options.profile_id, recover, resolvedApi, state.pending, state.snapshot]);

  const takeback = useCallback(async () => {
    const snapshot = state.snapshot;
    if (!snapshot || (state.pending && state.pending !== "engine") || !snapshot.capabilities.can_takeback) return;
    const id = ++requestId.current;
    setState((current) => ({ ...current, pending: "takeback", error: null }));
    try {
      const next = aiView(await resolvedApi.takeback(snapshot.id, snapshot.version, snapshot.engine_pending || snapshot.ply < 2 ? 1 : 2), options.profile_id);
      if (id === requestId.current) setState({ snapshot: next, pending: next.engine_pending ? "engine" : null, error: null });
    } catch (error: unknown) {
      await recover(snapshot.id, id, error);
    }
  }, [options.profile_id, recover, resolvedApi, state.pending, state.snapshot]);

  return useMemo(() => ({ ...state, move, takeback }), [move, state, takeback]);
}
