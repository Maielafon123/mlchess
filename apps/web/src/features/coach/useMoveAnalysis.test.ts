import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { AnalysisApi, AnalysisResult } from "../../api/analysisApi";
import type { GameSnapshot } from "../../api/gameApi";
import { useMoveAnalysis } from "./useMoveAnalysis";
import resultFixture from "../../../../../contracts/fixtures/analysis/result-cp-white.json";
import gameFixture from "../../../../../contracts/fixtures/game/snapshot-coach.json";

const game = { ...gameFixture, ply: 1 } as GameSnapshot;
const result = { ...resultFixture, game_id: game.id, revision: game.revision, ply: 1 } as AnalysisResult;

describe("move analysis lifecycle", () => {
  it("ignores a late result from the branch that was undone", async () => {
    let finishOld!: (value: AnalysisResult) => void;
    const old = new Promise<AnalysisResult>((resolve) => { finishOld = resolve; });
    const next = { ...result, revision: game.revision + 1, analysis_id: "new-analysis" };
    const api = { request: vi.fn().mockResolvedValueOnce({ id: result.analysis_id }).mockResolvedValueOnce({ id: next.analysis_id }),
      get: vi.fn().mockReturnValueOnce(old).mockResolvedValueOnce(next) } as unknown as AnalysisApi;
    const { result: hook, rerender } = renderHook(({ snapshot }) => useMoveAnalysis(snapshot, api), { initialProps: { snapshot: game } });
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(1));
    rerender({ snapshot: { ...game, revision: game.revision + 1 } });
    await waitFor(() => expect(hook.current.result?.analysis_id).toBe("new-analysis"));
    await act(async () => { finishOld(result); await old; });
    expect(hook.current.result?.analysis_id).toBe("new-analysis");
  });

  it("requests only the human move while the engine advances on the same branch", async () => {
    const api = { request: vi.fn().mockResolvedValue({ id: result.analysis_id }), get: vi.fn().mockResolvedValue(result) } as unknown as AnalysisApi;
    const { result: hook, rerender } = renderHook(({ snapshot }) => useMoveAnalysis(snapshot, api), { initialProps: { snapshot: game } });
    await waitFor(() => expect(hook.current.result).not.toBeNull());
    rerender({ snapshot: { ...game, ply: 2, version: game.version + 1 } });
    expect(api.request).toHaveBeenCalledTimes(1);
    rerender({ snapshot: { ...game, ply: 0, revision: game.revision + 1 } });
    expect(hook.current.result).toBeNull();
  });
});
