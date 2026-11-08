import { defineConfig, devices } from "@playwright/test";
import { randomUUID } from "node:crypto";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

// Real HTTP/WS and disposable SQLite; PostgreSQL races are a separate CI gate.
const root = fileURLToPath(new URL("../../", import.meta.url));
const database = join(tmpdir(), `mlchess-realtime-${randomUUID()}.db`).replaceAll("\\", "/");
export default defineConfig({
  testDir: "./tests/e2e/live", testMatch: "**/mobile.spec.ts", grep: /guest challenge/,
  outputDir: "./test-results/realtime", reporter: "list", workers: 1,
  use: { baseURL: "http://127.0.0.1:4175", trace: "retain-on-failure" },
  webServer: [
    { command: "python -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 58101 --no-access-log --log-level warning --no-proxy-headers --ws websockets --ws-max-size 2048 --ws-max-queue 4 --ws-per-message-deflate false", cwd: root, port: 58101,
      env: { MLCHESS_ENVIRONMENT: "test", MLCHESS_PUBLIC_ORIGIN: "http://127.0.0.1:4175", MLCHESS_DATABASE_URL: `sqlite+aiosqlite:///${database}`, MLCHESS_DATABASE_AUTO_CREATE: "true", MLCHESS_DEV_AUTH_ENABLED: "false", MLCHESS_INVITATION_SECRET: "x".repeat(43) } },
    { command: "pnpm build && pnpm exec vite preview --host 127.0.0.1 --port 4175", url: "http://127.0.0.1:4175", env: { VITE_AUTH_MODE: "guest", MLCHESS_DEV_API_TARGET: "http://127.0.0.1:58101" } },
  ],
  projects: [
    { name: "android-chromium", use: { ...devices["Pixel 7"], browserName: "chromium" } },
    { name: "iphone-webkit", use: { ...devices["iPhone 13"], browserName: "webkit" } },
  ],
});
