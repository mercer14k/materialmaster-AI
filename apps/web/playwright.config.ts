import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "../../tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 30000,
  use: {
    baseURL: "http://127.0.0.1:5297",
    viewport: { width: 1512, height: 1150 },
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  reporter: [["list"], ["html", { open: "never" }]],
  webServer: [
    {
      command: `${process.env.PYTHON || "python"} ../../tests/e2e/serve.py`,
      url: "http://127.0.0.1:8121/ready",
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: "pnpm dev --port 5297",
      url: "http://127.0.0.1:5297",
      env: { API_PROXY: "http://127.0.0.1:8121" },
      reuseExistingServer: false,
      timeout: 30000,
    },
  ],
});
