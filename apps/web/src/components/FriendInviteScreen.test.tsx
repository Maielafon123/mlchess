import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { FriendInviteScreen } from "../features/friend/FriendInviteScreen";

describe("FriendInviteScreen", () => {
  it("starts in a safe create-invite state", () => {
    render(<FriendInviteScreen api={{ create: vi.fn(), get: vi.fn(), accept: vi.fn() } as never} />);
    expect(screen.getByRole("button", { name: "Create private invite" })).toBeInTheDocument();
    expect(screen.getByText("No coach or analysis")).toBeInTheDocument();
  });

  it("renders the authoritative game snapshot after the invite becomes active", async () => {
    const inviteApi = { create: vi.fn().mockResolvedValue({ invite_id: "i", game_id: "g", state: "active", invite_url: "https://example.test/i", opponent: { display_name: "Opponent", connected: true }, clocks: null }), get: vi.fn(), accept: vi.fn() };
    const gameApi = { get: vi.fn().mockResolvedValue({ id: "g", status: "active", fen: "8/8/8/8/8/8/8/K6k w - - 0 1", moves: [], version: 1, revision: 0, capabilities: { can_move: false, can_resign: true } }), move: vi.fn(), resign: vi.fn(), create: vi.fn() };
    const user = userEvent.setup();
    render(<FriendInviteScreen api={inviteApi as never} gameApi={gameApi as never} />);
    await screen.findByRole("button", { name: "Create private invite" });
    await user.click(screen.getByRole("button", { name: "Create private invite" }));
    await waitFor(() => expect(gameApi.get).toHaveBeenCalledWith("g"));
    expect(await screen.findByRole("region", { name: "Game board" })).toBeInTheDocument();
  });
});
