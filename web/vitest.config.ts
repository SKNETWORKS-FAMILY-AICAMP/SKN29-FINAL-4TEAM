import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
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
