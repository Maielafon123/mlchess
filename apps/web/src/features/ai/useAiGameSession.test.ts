import { describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { acceptsEngineResult, useAiGameSession } from "./useAiGameSession";
import type { AiGameApi } from "../../api/aiGameApi";
import type { GameSnapshot } from "../../api/gameApi";

describe("AI result ordering", () => {
  it("accepts the current request at the same or newer server version", () => {
    expect(acceptsEngineResult(4, 4, 8, 8)).toBe(true);
    expect(acceptsEngineResult(4, 4, 8, 9)).toBe(true);
  });

  it("rejects stale request or version responses", () => {
    expect(acceptsEngineResult(5, 4, 8, 9)).toBe(false);
    expect(acceptsEngineResult(5, 5, 10, 9)).toBe(false);
  });
});

it("recovers when the worker commits before a pending takeback reaches the server", async () => {
  window.history.replaceState(null, "", "/play/ai");
  const snapshot: GameSnapshot = {
    schema_version: 1, id: "10000000-0000-4000-8000-000000000001", mode: "ai", status: "active", version: 1, revision: 0,
    fen: "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1", ply: 1, side_to_move: "black",
    players: [{ side: "white", kind: "human", user_id: "10000000-0000-4000-8000-000000000002" }, { side: "black", kind: "engine", user_id: null }],
    moves: [{ ply: 1, uci: "e2e4", san: "e4" }], time_control: null, clock: null,
    capabilities: { can_move: false, can_takeback: true, can_analyze_now: true }, result: null, termination: null,
  };
  const updated: GameSnapshot = { ...snapshot, version: 2, ply: 2, side_to_move: "white", fen: "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 2", moves: [...snapshot.moves, { ply: 2, uci: "e7e5", san: "e5" }], capabilities: { ...snapshot.capabilities, can_move: true } };
  const api = { createAi: vi.fn().mockResolvedValue(snapshot), takeback: vi.fn().mockRejectedValue(new Error("Stale position")), get: vi.fn().mockResolvedValue(updated) };
  const options = { profile_id: "club", side: "white" as const };
  const { result } = renderHook(() => useAiGameSession(options, api as unknown as AiGameApi));
  await waitFor(() => expect(result.current.snapshot?.version).toBe(1));
  await act(async () => { await result.current.takeback(); });
  expect(result.current.snapshot?.version).toBe(2);
  expect(result.current.snapshot?.capabilities.can_move).toBe(true);
  expect(result.current.pending).toBeNull();
  expect(api.get).toHaveBeenCalled();
});
