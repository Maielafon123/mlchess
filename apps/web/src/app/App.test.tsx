import { render, screen } from "@testing-library/react";
import { RouterProvider } from "react-router-dom";
import { router } from "./router";
import { I18nProvider } from "../i18n/I18nProvider";
import { AuthProvider } from "../auth/AuthProvider";

describe("web foundation routes", () => {
  it("renders the overview with navigation and primary actions", async () => {
    render(<I18nProvider><AuthProvider><RouterProvider router={router} /></AuthProvider></I18nProvider>);

    expect(await screen.findByRole("heading", { name: "Играйте, разбирайтесь, растите" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Начать партию" })).toHaveAttribute("href", "/play");
    expect(screen.getByRole("link", { name: "Открыть обучение" })).toHaveAttribute("href", "/learn");
  });
});
