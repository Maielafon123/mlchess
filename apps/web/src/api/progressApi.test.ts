import { describe, expect, it } from "vitest";
import { ProgressApi } from "./progressApi";

describe("ProgressApi", () => {
  it("returns skill progress and review dates", async () => { const snapshot = await new ProgressApi().get(); expect(snapshot.skills).toHaveLength(2); expect(snapshot.skills[0].due_at).toBeTruthy(); });
});
