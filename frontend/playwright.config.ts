import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:8000",
    trace: "retain-on-failure",
  },
  webServer: {
    // Overrides the persistent app-data volume with a fresh, throwaway one so
    // e2e mutations (add/rename/move/delete) never leak into a real dev board
    // and each run starts from a clean seeded DB.
    command:
      "docker compose -f docker-compose.yml -f docker-compose.e2e.yml up --build --force-recreate",
    cwd: "..",
    url: "http://127.0.0.1:8000/api/hello",
    reuseExistingServer: false,
    timeout: 180_000,
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
