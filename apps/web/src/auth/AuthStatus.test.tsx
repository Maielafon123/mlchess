import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { I18nProvider } from "../i18n/I18nProvider";
import { AuthProvider } from "./AuthProvider";
import { AuthStatus } from "./AuthStatus";

const fakeConfig = {
  mode: "fake" as const,
  mePath: "/api/v1/auth/me",
  loginPath: "/api/v1/auth/oidc/start",
  logoutPath: "/api/v1/auth/logout",
};

describe("AuthStatus", () => {
  it("supports guest notice, fake sign-in, and sign-out without a password form", async () => {
    const user = userEvent.setup();
    render(<I18nProvider><AuthProvider config={fakeConfig}><AuthStatus /></AuthProvider></I18nProvider>);

    expect(await screen.findByText("Гостевой режим: партии доступны, прогресс сохранится после входа.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/парол/i)).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Войти" }));
    expect(screen.getByText(/Demo student/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Выйти" }));
    expect(await screen.findByText("Гостевой режим: партии доступны, прогресс сохранится после входа.")).toBeInTheDocument();
  });
});
