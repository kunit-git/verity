import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Where the dev server proxies /api requests. Defaults to a backend running
// on the host; in Docker it is set to the backend service (http://backend:8000).
const proxyTarget = process.env.VITE_API_PROXY_TARGET || 'http://127.0.0.1:8000'

// Bind-mounted source on macOS/Windows Docker doesn't emit native fs events,
// so enable polling there to keep hot-reload working.
const usePolling = process.env.VITE_USE_POLLING === 'true'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    host: true,
    port: 5173,
    watch: usePolling ? { usePolling: true } : undefined,
    proxy: {
      '/api': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
