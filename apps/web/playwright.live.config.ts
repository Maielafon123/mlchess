import { defineConfig, devices } from "@playwright/test";

const baseURL = process.env.MLCHESS_LIVE_BASE_URL;
if (!baseURL) throw new Error("MLCHESS_LIVE_BASE_URL is required for test:e2e:live; refusing to run demo smoke tests");

export default defineConfig({
  testDir: "./tests/e2e/live",
  outputDir: "./test-results/live",
  fullyParallel: false,
  reporter: "list",
  use: { baseURL, trace: "retain-on-failure", ...devices["Desktop Chrome"] },
  projects: [{ name: "live-chromium", use: { ...devices["Desktop Chrome"] } }],
});
