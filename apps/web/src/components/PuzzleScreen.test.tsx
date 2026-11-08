import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PuzzleScreen } from "../features/learning/PuzzleScreen";
import { learningTransport } from "../test/learningFixtures";

describe("PuzzleScreen", () => {
  beforeEach(() => {
    // jsdom has no layout; react-chessboard needs a measured square to animate.
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 400, bottom: 400, width: 400, height: 400, toJSON: () => ({}) });
  });
  afterEach(() => vi.restoreAllMocks());
  it("reveals hints only after a server response, then loads a completed replay", async () => {
    const { puzzles } = learningTransport();
    render(<PuzzleScreen api={puzzles} />);
    expect(await screen.findByRole("heading", { name: "Back-rank finish" })).toBeInTheDocument();
    expect(screen.queryByText(/escape squares/)).not.toBeInTheDocument();
    expect(screen.queryByText("Your solution")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show next hint" }));
    expect(await screen.findByText(/escape squares/)).toBeInTheDocument();
    fireEvent.click(screen.getByText("Ввести ход с клавиатуры"));
    fireEvent.change(screen.getByLabelText("UCI move"), { target: { value: "d1d8" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(await screen.findByText("Your solution")).toBeInTheDocument();
    expect(screen.getByLabelText("UCI move")).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Restart puzzle" }));
    expect(await screen.findByText("Find mate in one.")).toBeInTheDocument();
  });
});
