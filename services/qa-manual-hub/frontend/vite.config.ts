import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// The dev server proxies /api to a locally running backend so the SPA behaves
// exactly as it does behind nginx in production (same origin, cookies included).
// Override the target with VITE_API_TARGET in .env.local when the backend runs
// somewhere other than the default port.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), 'VITE_')
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: env.VITE_API_TARGET ?? 'http://127.0.0.1:9180',
          changeOrigin: false,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: false,
      chunkSizeWarningLimit: 900,
    },
  }
})
