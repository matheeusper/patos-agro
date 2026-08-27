import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 300_000,
  expect: { timeout: 240_000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: process.env.PATOS_PAGES_URL || "http://127.0.0.1:8765/patos-agro/",
    acceptDownloads: true,
  },
  projects: [
    { name: "chromium", use: { browserName: "chromium" } },
    { name: "firefox", use: { browserName: "firefox" } },
  ],
});
