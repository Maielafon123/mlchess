import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CoachHintPanel } from "./CoachHintPanel";

describe("CoachHintPanel", () => {
  it("renders the five-level ladder disabled until a human move exists", () => {
    render(<CoachHintPanel context={null} />);
    expect(screen.getByRole("heading", { name: "Coach" })).toBeInTheDocument();
    expect(screen.getAllByRole("button")).toHaveLength(5);
    expect(screen.getAllByRole("button").every((button) => (button as HTMLButtonElement).disabled)).toBe(true);
  });
});
