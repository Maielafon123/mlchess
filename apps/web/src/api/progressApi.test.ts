import { describe, expect, it } from "vitest";
import { learningTransport } from "../test/learningFixtures";

describe("ProgressApi", () => {
  it("keeps the server's empty progress instead of inventing metrics", async () => {
    const { progress } = learningTransport();
    expect((await progress.get()).skills).toEqual([]);
    expect((await progress.review()).skills).toEqual([]);
  });
});
