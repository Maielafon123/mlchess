import { useEffect, useMemo, useState } from "react";
import { AnalysisApi, type AnalysisResult } from "../../api/analysisApi";
import { createIdempotencyKey } from "../../api/client";
import type { GameSnapshot } from "../../api/gameApi";

export function useMoveAnalysis(snapshot: GameSnapshot | null, api?: AnalysisApi) {
  const human = snapshot?.players.find((player) => player.kind !== "engine")?.side;
  const latest = snapshot?.ply ?? 0;
  const ply = human === "white" ? (latest % 2 ? latest : latest - 1) : (latest % 2 ? latest - 1 : latest);
  return usePositionAnalysis(snapshot, ply, api);
}

export function usePositionAnalysis(snapshot: GameSnapshot | null, ply: number, api?: AnalysisApi) {
  const resolvedApi = useMemo(() => api ?? new AnalysisApi(), [api]);
  const [retry, setRetry] = useState(0);
  const [state, setState] = useState<{ result: AnalysisResult | null; pending: boolean; error: string | null }>({ result: null, pending: false, error: null });
  const gameId = snapshot?.id;
  const revision = snapshot?.revision;
  const commandKey = useMemo(() => ({ gameId, revision, ply, retry, key: createIdempotencyKey() }), [gameId, revision, ply, retry]).key;
  useEffect(() => {
    if (!gameId || revision === undefined || ply < 1) { setState({ result: null, pending: false, error: null }); return; }
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    let attempts = 0;
    setState({ result: null, pending: true, error: null });
    const run = async () => {
      try {
        const accepted = await resolvedApi.request(gameId, ply, commandKey, controller.signal);
        const poll = async (): Promise<void> => {
          if (controller.signal.aborted) return;
          const wire = await resolvedApi.get(gameId, ply, controller.signal);
          if (controller.signal.aborted) return;
          if (wire.game_id !== gameId || wire.revision !== revision || wire.ply !== ply) throw new Error("Анализ относится к другой позиции.");
          if ("top_moves" in wire) {
            if (wire.analysis_id !== accepted.id) throw new Error("Обновите анализ этой позиции.");
            setState({ result: wire, pending: false, error: null });
          } else if (wire.status === "failed") throw new Error("Анализ временно недоступен. Попробуйте ещё раз позже.");
          else if (++attempts >= 30) throw new Error("Анализ ещё выполняется. Можно проверить его снова.");
          else timer = setTimeout(() => { void poll().catch(failed); }, 1000);
        };
        await poll();
      } catch (error) { failed(error); }
    };
    const failed = (error: unknown) => {
      if (!controller.signal.aborted) setState({ result: null, pending: false, error: error instanceof Error ? error.message : "Анализ недоступен." });
    };
    void run();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [commandKey, gameId, ply, resolvedApi, revision]);
  const result = state.result?.game_id === gameId && state.result?.revision === revision && state.result?.ply === ply ? state.result : null;
  return { ...state, result, retry: () => setRetry((value) => value + 1) };
}
