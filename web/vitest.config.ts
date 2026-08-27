import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import { normalizePath } from "vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: [
      {
        find: "../model/consultantWorkspaceMock",
        replacement: normalizePath(
          fileURLToPath(
            new URL(
              "./tests/fixtures/consultantWorkspaceMock.ts",
              import.meta.url,
            ),
          ),
        ),
      },
      {
        find: "../model/consultantNoticeMock",
        replacement: normalizePath(
          fileURLToPath(
            new URL(
              "./tests/fixtures/consultantNoticeMock.ts",
              import.meta.url,
            ),
          ),
        ),
      },
    ],
  },
  define: {
    "import.meta.env.VITE_USE_MOCK_API": JSON.stringify("true"),
    "import.meta.env.VITE_MOCK_DATASET": JSON.stringify("DESIGN_SCENARIOS"),
  },
  server: {
    fs: {
      allow: [".."],
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
    clearMocks: true,
  },
});
