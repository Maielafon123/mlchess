import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProgressDashboard } from "../features/learning/ProgressDashboard";

describe("ProgressDashboard", () => {
  it("shows server-graded skill metrics", async () => { render(<ProgressDashboard />); expect(await screen.findByRole("heading", { name: "Student progress" })).toBeInTheDocument(); expect(screen.getByText("Server graded")).toBeInTheDocument(); });
});
