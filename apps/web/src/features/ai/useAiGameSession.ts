import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AiGameApi, type AiGameOptions, type AiGameSnapshot } from "../../api/aiGameApi";

export type AiOperation = "creating" | "moving" | "takeback" | "engine" | null;
export type AiSessionState = { snapshot: AiGameSnapshot | null; pending: AiOperation; error: string | null };

/** Ignore a delayed engine response once a newer operation has changed the branch. */
export function acceptsEngineResult(activeRequestId: number, resultRequestId: number, activeVersion: number, resultVersion: number) {
  return activeRequestId === resultRequestId && resultVersion >= activeVersion;
}

function commandId() {
  return globalThis.crypto?.randomUUID?.() ?? `ai-move-${Date.now()}`;
}

export function useAiGameSession(options: AiGameOptions, api?: AiGameApi) {
  const resolvedApi = useMemo(() => api ?? new AiGameApi(), [api]);
  const requestId = useRef(0);
  const [state, setState] = useState<AiSessionState>({ snapshot: null, pending: "creating", error: null });

  useEffect(() => {
    const id = ++requestId.current;
    setState({ snapshot: null, pending: "creating", error: null });
    resolvedApi.createAi(options).then((snapshot) => {
      if (id === requestId.current) setState({ snapshot, pending: snapshot.engine_pending ? "engine" : null, error: null });
    }).catch((error: unknown) => {
      if (id === requestId.current) setState({ snapshot: null, pending: null, error: error instanceof Error ? error.message : "Unable to create AI game" });
    });
  }, [options, resolvedApi]);

  const move = useCallback(async (uci: string) => {
    const snapshot = state.snapshot;
    if (!snapshot || state.pending || !snapshot.capabilities.can_move) return;
    const id = ++requestId.current;
    setState((current) => ({ ...current, pending: "moving", error: null }));
    try {
      const next = await resolvedApi.move(snapshot.id, { uci, client_move_id: commandId(), expected_version: snapshot.version }) as AiGameSnapshot;
      if (!acceptsEngineResult(requestId.current, id, snapshot.version, next.version)) return;
      setState({ snapshot: next, pending: next.engine_pending ? "engine" : null, error: null });
    } catch (error: unknown) {
      if (id === requestId.current) setState((current) => ({ ...current, pending: null, error: error instanceof Error ? error.message : "Move rejected" }));
    }
  }, [resolvedApi, state.pending, state.snapshot]);

  const takeback = useCallback(async () => {
    const snapshot = state.snapshot;
    if (!snapshot || state.pending || !snapshot.capabilities.can_takeback) return;
    const id = ++requestId.current;
    setState((current) => ({ ...current, pending: "takeback", error: null }));
    try {
      const next = await resolvedApi.takeback(snapshot.id, snapshot.version);
      if (id === requestId.current) setState({ snapshot: next, pending: next.engine_pending ? "engine" : null, error: null });
    } catch (error: unknown) {
      if (id === requestId.current) setState((current) => ({ ...current, pending: null, error: error instanceof Error ? error.message : "Takeback rejected" }));
    }
  }, [resolvedApi, state.pending, state.snapshot]);

  return useMemo(() => ({ ...state, move, takeback }), [move, state, takeback]);
}
