import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MatchmakingScreen } from "../features/matchmaking/MatchmakingScreen";

describe("MatchmakingScreen", () => {
  it("starts with server-backed rating pools and no coach controls", () => {
    render(<MatchmakingScreen api={{ join: vi.fn(), get: vi.fn(), cancel: vi.fn(), game: vi.fn(), resign: vi.fn(), offerDraw: vi.fn() } as never} />);
    expect(screen.getByRole("button", { name: "Join rated queue" })).toBeInTheDocument();
    expect(screen.getByText("No coach or analysis")).toBeInTheDocument();
    expect(screen.getByText("Rapid 10+0")).toBeInTheDocument();
  });
});
