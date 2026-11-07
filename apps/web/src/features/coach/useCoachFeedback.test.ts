import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CoachApi } from "../../api/coachApi";
import { useCoachFeedback } from "./useCoachFeedback";

describe("useCoachFeedback", () => {
  it("polls pending jobs until ready", async () => {
    const api = { request: vi.fn().mockResolvedValue({ schema_version: 1, job_id: "j1", status: "pending", game_id: "g", analysis_id: "a", revision: 1, ply: 1, explanation: null }), get: vi.fn().mockResolvedValue({ schema_version: 1, job_id: "j1", status: "ready", game_id: "g", analysis_id: "a", revision: 1, ply: 1, explanation: { revision: 1, level: "observation", game_id: "g", analysis_id: "a", ply: 1 } }) } as unknown as CoachApi;
    const { result } = renderHook(() => useCoachFeedback(api));
    await act(async () => { await result.current.requestFeedback({ game_id: "g", analysis_id: "a", revision: 1, ply: 1, language: "en" }, "observation"); });
    expect(api.get).toHaveBeenCalledWith("g", "j1");
    expect(result.current.explanation?.level).toBe("observation");
  });
});
