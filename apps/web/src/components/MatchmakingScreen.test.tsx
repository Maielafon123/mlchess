import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { MatchmakingScreen } from "../features/matchmaking/MatchmakingScreen";

describe("MatchmakingScreen", () => {
  it("shows the account's real rating and no coach controls", async () => {
    const pools = vi.fn().mockResolvedValue({ items: [{ pool: "rapid-10+0", your_rating: 1284 }] });
    render(<MatchmakingScreen eligible api={{ pools, current: vi.fn().mockResolvedValue({ ticket: null }) } as never} />);
    expect(await screen.findByRole("button", { name: "Найти соперника" })).toBeInTheDocument();
    expect(screen.getByText("Без подсказок")).toBeInTheDocument();
    expect(screen.getByText("Ваш рейтинг 1284")).toBeInTheDocument();
    expect(screen.getByText("Рапид 10+0")).toBeInTheDocument();
  });

  it("offers guests an unranked game without requesting a ticket", () => {
    const pools = vi.fn();
    render(<MatchmakingScreen api={{ pools } as never} />);
    expect(screen.getByRole("link", { name: "Сыграть с другом без регистрации" })).toHaveAttribute("href", "/play/friend");
    expect(screen.queryByRole("button", { name: "Найти соперника" })).not.toBeInTheDocument();
    expect(pools).not.toHaveBeenCalled();
  });
});
