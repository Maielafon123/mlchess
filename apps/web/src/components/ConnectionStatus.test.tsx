import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConnectionStatus } from "./ConnectionStatus";

describe("ConnectionStatus", () => {
  it("explains out-of-sync state", () => { render(<ConnectionStatus state="out-of-sync" />); expect(screen.getByRole("status")).toHaveTextContent("out of sync"); });
});
