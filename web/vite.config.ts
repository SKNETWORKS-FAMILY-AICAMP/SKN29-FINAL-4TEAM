import { defineConfig, loadEnv, normalizePath } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { designPreviewPlugin } from './preview/designPreviewPlugin.ts'

// https://vite.dev/config/
export default defineConfig(({ mode, command }) => {
  const isDesignPreview = command === "serve" && mode === "design"
  const env = loadEnv(mode, process.cwd(), "")
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || "http://127.0.0.1:8000"
  const developmentMockModule = normalizePath(
    fileURLToPath(
      new URL("./tests/fixtures/consultantWorkspaceMock.ts", import.meta.url),
    ),
  )
  const developmentNoticeMockModule = normalizePath(
    fileURLToPath(
      new URL("./tests/fixtures/consultantNoticeMock.ts", import.meta.url),
    ),
  )

  return {
    plugins: [react(), ...(isDesignPreview ? [designPreviewPlugin()] : [])],
    resolve: {
      alias:
        mode === "production" || mode === "design"
          ? []
          : [
              {
                find: "../model/consultantWorkspaceMock",
                replacement: developmentMockModule,
              },
              {
                find: "../model/consultantNoticeMock",
                replacement: developmentNoticeMockModule,
              },
            ],
    },
    server: {
      host: isDesignPreview ? "127.0.0.1" : undefined,
      allowedHosts: [".trycloudflare.com"],
      fs: {
        allow: [".."],
      },
      // A missing sample response must never fall through to the real API.
      proxy: isDesignPreview ? undefined : {
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
