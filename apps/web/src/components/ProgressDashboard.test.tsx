import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressDashboard } from "../features/learning/ProgressDashboard";

describe("ProgressDashboard", () => {
  it("labels the local demo metrics honestly", async () => { render(<ProgressDashboard />); expect(await screen.findByRole("heading", { name: "Student progress" })).toBeInTheDocument(); expect(screen.getByText(/Demo data/)).toBeInTheDocument(); });
});
