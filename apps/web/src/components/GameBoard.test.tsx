import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { GameBoard } from "./GameBoard";

vi.mock("react-chessboard", () => ({
  Chessboard: ({ options }: { options: { squareStyles?: Record<string, unknown>; onSquareClick: (event: { square: string }) => void } }) => (
    <div data-testid="chessboard" data-highlighted={Object.keys(options.squareStyles ?? {}).join(",")}>
      <button type="button" onClick={() => options.onSquareClick({ square: "e2" })}>e2</button>
      <button type="button" onClick={() => options.onSquareClick({ square: "e4" })}>e4</button>
    </div>
  ),
}));

describe("GameBoard", () => {
  it("shows move history and emits a legal click move without owning game state", () => {
    const onMoveAttempt = vi.fn();
    render(<GameBoard fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" moves={[{ ply: 1, san: "e4", uci: "e2e4" }]} onMoveAttempt={onMoveAttempt} />);

    expect(within(screen.getByLabelText("Move history")).getByText("e4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "e2" }));
    expect(screen.getByTestId("chessboard").dataset.highlighted?.split(",").sort()).toEqual(["e2", "e3", "e4"]);
    fireEvent.click(screen.getByRole("button", { name: "e4" }));
    expect(onMoveAttempt).toHaveBeenCalledWith("e2e4");
  });

  it("accepts keyboard UCI input for a legal move", () => {
    const onMoveAttempt = vi.fn();
    render(<GameBoard fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" moves={[]} onMoveAttempt={onMoveAttempt} />);
    const input = screen.getByLabelText("UCI move");
    fireEvent.change(input, { target: { value: "e2e4" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onMoveAttempt).toHaveBeenCalledWith("e2e4");
  });
});
