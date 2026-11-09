import { act, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { PlayerClocks } from "./PlayerClocks";
import type { GameSnapshot } from "../api/gameApi";

afterEach(() => vi.useRealTimers());

it("projects only the running side, then adopts a stopped server clock", () => {
  vi.useFakeTimers({ toFake: ["performance", "setInterval", "clearInterval"] });
  const clock: NonNullable<GameSnapshot["clock"]> = { white_remaining_ms: 1100, black_remaining_ms: 2000, running_side: "white", server_now: "2026-11-09T00:00:00Z" };
  const { rerender } = render(<PlayerClocks clock={clock} />);
  expect(screen.getByRole("timer", { name: "Часы белых" })).toHaveTextContent("00:02");
  act(() => vi.advanceTimersByTime(1200));
  expect(screen.getByRole("timer", { name: "Часы белых" })).toHaveTextContent("00:00");
  expect(screen.getByRole("timer", { name: "Часы чёрных" })).toHaveTextContent("00:02");
  rerender(<PlayerClocks clock={{ ...clock, white_remaining_ms: 0, running_side: null }} />);
  act(() => vi.advanceTimersByTime(5000));
  expect(screen.getByRole("timer", { name: "Часы чёрных" })).toHaveTextContent("00:02");
});
