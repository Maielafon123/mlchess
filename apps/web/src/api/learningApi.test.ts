import { describe, expect, it } from "vitest";
import { sanitizeLessonText, sanitizeLesson } from "./learningApi";
import { lesson, learningTransport } from "../test/learningFixtures";

describe("learning catalog", () => {
  it("cleans imported markup and blocks non-HTTPS provenance links", () => {
    expect(sanitizeLessonText("<script>alert(1)</script> Center")).toBe("alert(1) Center");
    expect(sanitizeLesson({ ...lesson, source_url: "javascript:alert(1)" }).source_url).toBe("");
  });
  it("loads locale-specific pages and saves status with a reset fence", async () => {
    const { learning, fetchImpl } = learningTransport();
    await learning.list(2, 6, "en");
    expect(String(fetchImpl.mock.calls[0][0])).toContain("page=2&page_size=6&language=en");
    const saved = await learning.status("opening-center", "completed", 3, "en");
    expect(saved.status).toBe("completed");
    expect(JSON.parse(String(fetchImpl.mock.calls[1][1]?.body))).toEqual({ schema_version: 1, learning_epoch: 3, status: "completed" });
  });
});
