import { describe, expect, it } from "vitest";
import { LearningApi, sanitizeLessonText } from "./learningApi";

describe("learning catalog", () => {
  it("sanitizes markup and unsafe urls", async () => {
    expect(sanitizeLessonText("<script>alert(1)</script> Center")).toBe("alert(1) Center");
    const result = await new LearningApi().list();
    expect(result.items[0].license).toBe("CC BY 4.0");
    expect(result.items[0].source_url.startsWith("https://")).toBe(true);
  });
});
