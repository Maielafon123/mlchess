import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LessonCatalog } from "../features/learning/LessonCatalog";
import { learningTransport } from "../test/learningFixtures";

describe("LessonCatalog", () => {
  it("shows provenance and waits for the server to persist completion", async () => {
    const { learning, fetchImpl } = learningTransport();
    render(<LessonCatalog api={learning} />);
    expect(await screen.findByText("Центр в дебюте")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Open lesson" }));
    expect(await screen.findByText(/Source:/)).toBeInTheDocument();
    await screen.findAllByText("started");
    fireEvent.click(screen.getByRole("button", { name: "Mark completed" }));
    expect(await screen.findByRole("button", { name: "Mark completed" })).toBeDisabled();
    expect(fetchImpl.mock.calls.filter(([, init]) => init?.method === "POST")).toHaveLength(2);
  });
});
