import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { PostGameReport } from "./PostGameReport";

vi.mock("react-chessboard", () => ({ Chessboard: () => <div data-testid="chessboard" /> }));

describe("PostGameReport", () => {
  it("shows partial status without inventing decisions", () => {
    render(<PostGameReport report={{ game_id: "g1", status: "partial", result: "unknown", analyzed_plies: 1, total_plies: 4, decisions: [] }} />);
    expect(screen.getByRole("status")).toHaveTextContent("1/4");
    expect(screen.getByText("No verified critical decisions in this filter.")).toBeInTheDocument();
  });
});
