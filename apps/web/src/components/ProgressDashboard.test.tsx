import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressDashboard } from "../features/learning/ProgressDashboard";
import { learningTransport } from "../test/learningFixtures";

describe("ProgressDashboard", () => {
  it("shows an honest empty state for a new student", async () => {
    render(<ProgressDashboard api={learningTransport().progress} />);
    expect(await screen.findByText(/Solve your first puzzle/)).toBeInTheDocument();
    expect(screen.queryByText(/Demo data/)).not.toBeInTheDocument();
  });
});
