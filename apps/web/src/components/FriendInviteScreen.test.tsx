import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { FriendInviteScreen } from "../features/friend/FriendInviteScreen";

describe("FriendInviteScreen", () => {
  it("starts in a safe create-invite state", () => {
    render(<FriendInviteScreen api={{ create: vi.fn(), get: vi.fn(), accept: vi.fn() } as never} />);
    expect(screen.getByRole("button", { name: "Create private invite" })).toBeInTheDocument();
    expect(screen.getByText("No coach or analysis")).toBeInTheDocument();
  });
});
