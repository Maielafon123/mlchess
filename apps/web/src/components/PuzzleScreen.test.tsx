import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PuzzleScreen } from "../features/learning/PuzzleScreen";

describe("PuzzleScreen", () => {
  it("loads the puzzle and exposes progressive hints", async () => {
    render(<PuzzleScreen />);
    expect(await screen.findByRole("heading", { name: "Back-rank finish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Show next hint" })).toBeEnabled();
    expect(screen.queryByText(/Look at the opponent/)).not.toBeInTheDocument();
  });
});
