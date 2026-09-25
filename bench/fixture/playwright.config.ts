import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  webServer: {
    command: "node --import tsx ./src/server.ts",
    port: 3000,
    reuseExistingServer: false,
  },
  use: { baseURL: "http://localhost:3000" },
});
