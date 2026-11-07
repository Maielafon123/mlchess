import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LessonCatalog } from "../features/learning/LessonCatalog";

describe("LessonCatalog", () => {
  it("renders provenance-backed demo lessons", async () => {
    render(<LessonCatalog />);
    expect(await screen.findByText("Центр в дебюте")).toBeInTheDocument();
    expect(screen.queryByText("CC BY 4.0")).not.toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "Open lesson" })[0]);
    expect(await screen.findByText(/Source:/)).toBeInTheDocument();
  });
});
