import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LessonCatalog } from "../features/learning/LessonCatalog";
import { learningTransport } from "../test/learningFixtures";

describe("LessonCatalog", () => {
  beforeEach(() => {
    vi.spyOn(HTMLElement.prototype, "getBoundingClientRect").mockReturnValue({ x: 0, y: 0, top: 0, left: 0, right: 400, bottom: 400, width: 400, height: 400, toJSON: () => ({}) });
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows provenance and waits for the server to persist completion", async () => {
    const { learning, fetchImpl } = learningTransport();
    render(<LessonCatalog api={learning} />);
    expect(await screen.findByText("Центр в дебюте")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open lesson" }));
    expect(await screen.findByText(/Source:/)).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Game board" })).toBeVisible();
    fireEvent.click(screen.getByText("Ввести ход с клавиатуры"));
    fireEvent.change(screen.getByLabelText("UCI move"), { target: { value: "d2d4" } });
    fireEvent.click(screen.getByRole("button", { name: "Submit" }));
    expect(screen.getByText("d4")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Show example" }));
    expect(screen.getByText("Nf3")).toBeVisible();
    expect(screen.queryByText("d4")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Reset position" }));
    expect(screen.getByText("No moves yet.")).toBeVisible();
    await screen.findAllByText("started");
    fireEvent.click(screen.getByRole("button", { name: "Mark completed" }));
    expect(await within(screen.getByRole("article", { name: "Lesson detail" })).findByText("completed")).toBeVisible();
    expect(screen.getByRole("button", { name: "Mark completed" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Back to lessons" }));
    expect(screen.getByRole("button", { name: "Open lesson" })).toHaveFocus();
    expect(fetchImpl.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2);
  });
});
