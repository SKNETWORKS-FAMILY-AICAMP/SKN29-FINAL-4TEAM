import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const backendTarget = env.VITE_BACKEND_PROXY_TARGET || "http://127.0.0.1:8000"

  return {
    plugins: [react()],
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
