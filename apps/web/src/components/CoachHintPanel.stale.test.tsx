import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CoachHintPanel } from "./CoachHintPanel";

const feedback = vi.hoisted(() => ({ requestFeedback: vi.fn(), invalidate: vi.fn(), pending: false, error: null,
  explanation: { game_id: "game", analysis_id: "old", revision: 1, ply: 1, language: "en", level: "observation", summary: "Old branch hint", why: "Verified earlier", question: "Earlier question", fallback_used: false } }));
vi.mock("../features/coach/useCoachFeedback", () => ({ useCoachFeedback: () => feedback }));

describe("coach context change", () => {
  it("hides an old explanation synchronously when the analysis identity changes", () => {
    const context = { game_id: "game", analysis_id: "old", revision: 1, ply: 1, language: "en" as const };
    const { rerender } = render(<CoachHintPanel context={context} autoObservation={false} />);
    expect(screen.getByText("Old branch hint")).toBeInTheDocument();
    rerender(<CoachHintPanel context={{ ...context, analysis_id: "new" }} autoObservation={false} />);
    expect(screen.queryByText("Old branch hint")).not.toBeInTheDocument();
  });
});
