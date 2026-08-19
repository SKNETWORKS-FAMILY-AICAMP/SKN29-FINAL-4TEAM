import { defineConfig, devices } from "@playwright/test";

const DEFAULT_WEB_BASE_URL = "http://127.0.0.1:4173";
const DEFAULT_BACKEND_BASE_URL = "http://127.0.0.1:8000";
const suppliedWebBaseUrl = process.env.E2E_WEB_BASE_URL?.trim();
const webBaseUrl = suppliedWebBaseUrl || DEFAULT_WEB_BASE_URL;
const backendBaseUrl =
  process.env.E2E_BACKEND_BASE_URL?.trim() || DEFAULT_BACKEND_BASE_URL;

export default defineConfig({
  testDir: "./e2e/specs",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: Boolean(process.env.CI),
  globalTimeout: 300_000,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  outputDir: ".runtime/playwright/test-results",
  reporter: [["list"]],
  globalSetup: "./e2e/support/globalSetup.ts",
  globalTeardown: "./e2e/support/globalTeardown.ts",
  use: {
    baseURL: webBaseUrl,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    screenshot: "off",
    trace: {
      mode: "retain-on-failure",
      attachments: false,
      screenshots: false,
      snapshots: false,
      sources: false,
    },
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: suppliedWebBaseUrl
    ? undefined
    : {
        command:
          "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort",
        url: webBaseUrl,
        reuseExistingServer: false,
        timeout: 120_000,
        env: {
          ...process.env,
          VITE_API_BASE_URL: "/api/v1",
          VITE_BACKEND_PROXY_TARGET: backendBaseUrl,
          VITE_ENABLE_DESIGN_MOCK_FALLBACK: "false",
          VITE_MOCK_AUTHENTICATED: "false",
          VITE_USE_MOCK_API: "false",
        },
      },
});
