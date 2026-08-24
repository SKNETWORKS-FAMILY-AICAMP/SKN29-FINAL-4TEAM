import { defineConfig, loadEnv, normalizePath } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || "http://127.0.0.1:8000"
  const developmentMockModule = normalizePath(
    fileURLToPath(
      new URL("./tests/fixtures/consultantWorkspaceMock.ts", import.meta.url),
    ),
  )

  return {
    plugins: [react()],
    resolve: {
      alias:
        mode === "production"
          ? []
          : [
              {
                find: "../model/consultantWorkspaceMock",
                replacement: developmentMockModule,
              },
            ],
    },
    server: {
      allowedHosts: [".trycloudflare.com"],
      fs: {
        allow: [".."],
      },
      proxy: {
        "/api": {
          target: backendTarget,
          changeOrigin: true,
        },
        "/health": {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
  }
})
